#!/usr/bin/env python3
"""
Commit-Aware Regression Checker and CI Gate.
Adheres strictly to Phase 15 requirements:
- Inspects changed paths between commit SHAs (base vs head)
- Maps changed components to focused test suites
- Runs focused regression first, followed by required full regression
- Produces sanitized, auditable execution reports
- Gated exit codes (0 on green, 1 on regression)
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Mapping of source path prefixes to focused test suites
SUBSYSTEM_TEST_MAP: dict[str, list[str]] = {
    "backend/sandbox": [
        "tests/unit/test_sandbox_validator.py",
        "tests/unit/test_sandbox_sanitizer.py",
        "tests/unit/test_sandbox_service.py",
        "tests/integration/test_sandbox_execution.py",
        "tests/adversarial/test_adversarial_sandbox.py",
    ],
    "backend/scoring": [
        "tests/unit/test_scoring_calculator.py",
        "tests/unit/test_scoring_rules.py",
        "tests/unit/test_scoring_weights.py",
        "tests/integration/test_scoring_reproducibility.py",
        "tests/adversarial/test_adversarial_pipeline.py",
    ],
    "backend/runtime": [
        "tests/unit/test_runtime_builder.py",
        "tests/unit/test_runtime_models.py",
        "tests/unit/test_cli_evaluator.py",
        "tests/unit/test_http_evaluator.py",
        "tests/unit/test_library_evaluator.py",
        "tests/unit/test_worker_evaluator.py",
        "tests/integration/test_runtime_dispatcher.py",
    ],
    "backend/analyzers": [
        "tests/unit/test_ast_metrics_analyzer.py",
        "tests/unit/test_dependency_scanner.py",
        "tests/unit/test_python_linter.py",
        "tests/unit/test_secret_scanner.py",
        "tests/unit/test_normalizer.py",
        "tests/integration/test_analyzer_registry.py",
    ],
    "backend/repository": [
        "tests/unit/test_detector.py",
        "tests/unit/test_snapshot.py",
        "tests/unit/test_validator.py",
        "tests/integration/test_ingestion_service.py",
        "tests/adversarial/test_adversarial_security.py",
    ],
    "backend/api": [
        "tests/integration/test_health_routes.py",
        "tests/integration/test_evaluation_routes.py",
        "tests/integration/test_repository_routes.py",
        "tests/integration/test_dashboard_routes.py",
        "tests/integration/test_correlation_middleware.py",
    ],
    "backend/ai": [
        "tests/unit/test_ai_models.py",
        "tests/unit/test_ai_prompts.py",
        "tests/unit/test_ai_providers.py",
        "tests/integration/test_ai_service.py",
    ],
    "backend/pipeline": [
        "tests/integration/test_pipeline_e2e.py",
        "tests/adversarial/test_adversarial_pipeline.py",
    ],
    "backend/static": [
        "tests/integration/test_dashboard_routes.py",
    ],
    "backend/database": [
        "tests/integration/test_pipeline_e2e.py",
        "tests/integration/test_evaluation_routes.py",
    ],
    "backend/observability": [
        "tests/unit/test_logger.py",
        "tests/unit/test_observability.py",
        "tests/integration/test_correlation_middleware.py",
        "tests/integration/test_health_routes.py",
    ],
}


def sanitize_text(text: str) -> str:
    """Sanitize secrets and credentials from outputs."""
    # Redact GitHub tokens
    text = re.sub(r"ghp_[A-Za-z0-9_]{36,}", "[REDACTED_GH_TOKEN]", text)
    # Redact AWS keys
    text = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]", text)
    # Redact database connection strings
    text = re.sub(
        r"postgresql://[^:]+:[^@]+@", "postgresql://[REDACTED_USER]:[REDACTED_PASS]@", text
    )
    return text


def get_git_diff_files(base_sha: str | None = None, head_sha: str | None = None) -> list[str]:
    """Inspect changed files using git diff."""
    cmd = ["git", "diff", "--name-only"]
    if base_sha and head_sha:
        cmd.extend([base_sha, head_sha])
    elif base_sha:
        cmd.append(base_sha)
    else:
        cmd.extend(["HEAD~1", "HEAD"])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        return files
    except subprocess.CalledProcessError:
        # Fallback to porcelain status if diff fails (e.g., initial commit or dirty working copy)
        proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        files = []
        for line in proc.stdout.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                files.append(parts[1])
        return files


def map_files_to_test_targets(files: list[str]) -> tuple[list[str], set[str]]:
    """Determine focused test files based on modified paths."""
    matched_targets: set[str] = set()
    affected_subsystems: set[str] = set()

    for file_path in files:
        normalized = file_path.replace("\\", "/")
        # If test itself modified, include it directly
        if normalized.startswith("tests/") and normalized.endswith(".py"):
            matched_targets.add(normalized)
            continue

        # Match subsystem prefixes
        for prefix, tests in SUBSYSTEM_TEST_MAP.items():
            if normalized.startswith(prefix):
                affected_subsystems.add(prefix)
                for t in tests:
                    matched_targets.add(t)

    return sorted(matched_targets), affected_subsystems


def run_pytest(target_args: list[str]) -> tuple[int, str, float]:
    """Execute pytest on target arguments and record duration and output."""
    t0 = time.monotonic()
    cmd = [sys.executable, "-m", "pytest", "-q"] + target_args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.monotonic() - t0
        output = sanitize_text(proc.stdout + ("\n" + proc.stderr if proc.stderr else ""))
        return proc.returncode, output, round(duration, 2)
    except Exception as exc:
        duration = time.monotonic() - t0
        return 1, f"Failed to execute pytest: {exc}", round(duration, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="RepoScore Commit-Aware Regression Checker")
    parser.add_argument(
        "--base-sha", type=str, default=None, help="Base commit SHA (e.g. PR target)"
    )
    parser.add_argument(
        "--head-sha", type=str, default=None, help="Head commit SHA (e.g. PR source)"
    )
    parser.add_argument("--output-json", type=str, default=None, help="Output path for JSON report")
    parser.add_argument(
        "--output-md", type=str, default=None, help="Output path for Markdown summary"
    )
    parser.add_argument("--skip-full-suite", action="store_true", help="Skip full test suite pass")
    args = parser.parse_args()

    print("=================================================================")
    print(" RepoScore Commit-Aware Regression Gate")
    print(f" Timestamp: {datetime.now(UTC).isoformat()}")
    print("=================================================================")

    # 1. Identify changed files
    changed_files = get_git_diff_files(args.base_sha, args.head_sha)
    print(f"Inspected {len(changed_files)} changed file(s):")
    for f in changed_files[:15]:
        print(f"  - {f}")
    if len(changed_files) > 15:
        print(f"  ... and {len(changed_files) - 15} more files.")

    # 2. Map files to test targets
    focused_targets, affected_subsystems = map_files_to_test_targets(changed_files)
    print(
        f"\nAffected Subsystems: {', '.join(sorted(affected_subsystems)) if affected_subsystems else 'None (General/Docs)'}"
    )
    print(f"Focused Test Targets: {len(focused_targets)} file(s)")

    # 3. Run focused tests
    focused_passed = True
    focused_result = {"exit_code": 0, "duration_s": 0.0, "output": "No focused tests required."}

    if focused_targets:
        print(f"\n[1/2] Running Focused Regression Tests ({len(focused_targets)} targets)...")
        code, out, dur = run_pytest(focused_targets)
        focused_result = {"exit_code": code, "duration_s": dur, "output": out}
        print(f"Focused tests exited with code {code} ({dur}s).")
        print(out.strip())
        if code != 0:
            focused_passed = False
            print("ERROR: Focused regression tests FAILED!")
    else:
        print("\n[1/2] No subsystem test targets identified for changed files.")

    # 4. Run required full regression suite
    full_passed = True
    full_result = {"exit_code": 0, "duration_s": 0.0, "output": "Full suite skipped."}

    if not args.skip_full_suite:
        print("\n[2/2] Running Required Full Regression Suite (tests/)...")
        code, out, dur = run_pytest(["tests/"])
        full_result = {"exit_code": code, "duration_s": dur, "output": out}
        print(f"Full regression suite exited with code {code} ({dur}s).")
        print(out.strip())
        if code != 0:
            full_passed = False
            print("ERROR: Full regression suite FAILED!")

    overall_passed = focused_passed and full_passed

    # 5. Build structured report
    report_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "base_sha": args.base_sha,
        "head_sha": args.head_sha,
        "changed_files_count": len(changed_files),
        "changed_files": changed_files,
        "affected_subsystems": sorted(affected_subsystems),
        "focused_targets": focused_targets,
        "focused_result": focused_result,
        "full_result": full_result,
        "overall_status": "PASS" if overall_passed else "FAIL",
    }

    # 6. Save JSON report if requested
    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        print(f"\nJSON report written to: {out_p}")

    # 7. Save Markdown summary if requested
    if args.output_md:
        md_lines = [
            "# RepoScore CI Regression Gate Summary",
            "",
            f"- **Timestamp:** {report_data['timestamp']}",
            f"- **Status:** {'🟢 PASS' if overall_passed else '🔴 FAIL'}",
            f"- **Base SHA:** `{args.base_sha or 'N/A'}`",
            f"- **Head SHA:** `{args.head_sha or 'N/A'}`",
            f"- **Changed Files:** {len(changed_files)}",
            f"- **Affected Subsystems:** {', '.join(report_data['affected_subsystems']) or 'None'}",
            "",
            "## Test Results",
            f"- **Focused Suite:** {'PASS' if focused_passed else 'FAIL'} ({focused_result['duration_s']}s)",
            f"- **Full Regression Suite:** {'PASS' if full_passed else 'FAIL'} ({full_result['duration_s']}s)",
            "",
            "### Output Snippet",
            "```",
            (
                str(full_result.get("output", "")).strip()[-1000:]
                if len(str(full_result.get("output", ""))) > 1000
                else str(full_result.get("output", "")).strip()
            ),
            "```",
        ]
        out_md_p = Path(args.output_md)
        out_md_p.parent.mkdir(parents=True, exist_ok=True)
        out_md_p.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"Markdown report written to: {out_md_p}")

    print("\n=================================================================")
    print(f" Final CI Gate Result: {'PASS' if overall_passed else 'FAIL'}")
    print("=================================================================")

    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
