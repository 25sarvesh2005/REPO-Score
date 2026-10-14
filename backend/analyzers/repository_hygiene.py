"""
Repository Hygiene and Structural Soundness Static Analyzer.
Adheres strictly to ADR-003, ADR-008, and SCORING_ARCHITECTURE.md.
Empirically assesses documentation presence, test suite existence, CI/CD automation,
and dependency lockfile hygiene without executing untrusted code.
"""

import os
from pathlib import Path
from typing import Any

from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import (
    AnalyzerCategory,
    AnalyzerMetadata,
    FindingLocation,
    NormalizedFinding,
)
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel

TEST_FILE_PATTERNS = (
    "test_",
    "_test.",
    ".test.",
    ".spec.",
    "Test.",
)

TEST_DIR_NAMES = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
}

LOCKFILE_NAMES = {
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "Cargo.lock",
    "go.sum",
}

MANIFEST_NAMES = {
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
}


class RepositoryHygieneAnalyzer(BaseAnalyzer):
    """
    Evaluates repository engineering fundamentals: documentation, automated testing,
    CI/CD configuration, and dependency pinning. Emits canonical normalized findings.
    """

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="repository-hygiene",
            name="Repository Hygiene & Structural Soundness Analyzer",
            version="1.0.0",
            category=AnalyzerCategory.ARCHITECTURE,
            target_languages=["*"],
            description="Empirically verifies presence of README documentation, automated test files, CI/CD workflows, and lockfiles.",
        )

    def can_analyze(self, tech_stack: dict[str, Any]) -> bool:
        return True

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        resolved_root = snapshot_path.resolve()

        has_readme = False
        has_tests = False
        has_ci_cd = False
        has_manifest = False
        has_lockfile = False
        unpinned_deps: list[str] = []

        # Check CI/CD paths
        github_workflows = resolved_root / ".github" / "workflows"
        if (
            github_workflows.exists()
            and any(github_workflows.iterdir())
            or (resolved_root / ".gitlab-ci.yml").exists()
            or (resolved_root / "azure-pipelines.yml").exists()
            or (resolved_root / "Jenkinsfile").exists()
            or (resolved_root / ".circleci").exists()
        ):
            has_ci_cd = True

        for root, dirs, files in os.walk(resolved_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in {"node_modules", "venv", ".venv", "build", "dist", "__pycache__"}
            ]

            # Check for test directories
            for d in dirs:
                if d.lower() in TEST_DIR_NAMES:
                    has_tests = True

            for f in files:
                f_lower = f.lower()

                # Documentation check
                if f_lower.startswith("readme") and not has_readme:
                    f_path = Path(root) / f
                    try:
                        if f_path.stat().st_size > 50:
                            has_readme = True
                    except Exception:
                        pass

                # Test file check
                if any(p in f_lower for p in TEST_FILE_PATTERNS):
                    has_tests = True

                # Manifest check
                if f in MANIFEST_NAMES:
                    has_manifest = True
                    # Check for unpinned requirements.txt
                    if f == "requirements.txt":
                        try:
                            content = (Path(root) / f).read_text(encoding="utf-8", errors="replace")
                            for line in content.splitlines():
                                clean = line.strip().split("#")[0]
                                if clean and not clean.startswith("-"):
                                    if "==" not in clean and "@" not in clean:
                                        pkg = (
                                            clean.split()[0]
                                            .split(">")[0]
                                            .split("<")[0]
                                            .split("~")[0]
                                        )
                                        unpinned_deps.append(pkg)
                        except Exception:
                            pass

                # Lockfile check
                if f in LOCKFILE_NAMES:
                    has_lockfile = True

        # 1. Missing Documentation Finding
        if not has_readme:
            findings.append(
                NormalizedFinding(
                    analyzer_id="repository-hygiene",
                    tool_version=self.metadata.version,
                    rule_id="RULE-DOC-MISSING-README",
                    category=EvidenceCategory.DOCUMENTATION,
                    severity=SeverityLevel.HIGH,
                    confidence=1.0,
                    title="Missing Repository Documentation / README",
                    description="Repository does not contain a comprehensive README file explaining setup, usage, and architecture.",
                    recommendation="Add a descriptive README.md at repository root documenting project purpose, quickstart, and testing instructions.",
                    location=FindingLocation(file_path="README.md", start_line=1, end_line=1),
                )
            )

        # 2. Missing Automated Test Files Finding
        if not has_tests:
            findings.append(
                NormalizedFinding(
                    analyzer_id="repository-hygiene",
                    tool_version=self.metadata.version,
                    rule_id="RULE-TEST-NO-TEST-FILES",
                    category=EvidenceCategory.TESTING,
                    severity=SeverityLevel.HIGH,
                    confidence=1.0,
                    title="Zero Automated Test Files Found",
                    description="No automated unit, integration, or end-to-end test files or directories detected across repository.",
                    recommendation="Implement automated tests using standard test frameworks (e.g. pytest, jest, vitest, or go test) to prevent regressions.",
                    location=FindingLocation(file_path="tests/", start_line=1, end_line=1),
                )
            )

        # 3. Missing CI/CD Workflow Finding
        if not has_ci_cd:
            findings.append(
                NormalizedFinding(
                    analyzer_id="repository-hygiene",
                    tool_version=self.metadata.version,
                    rule_id="RULE-ENG-NO-CI-WORKFLOW",
                    category=EvidenceCategory.ENGINEERING_MATURITY,
                    severity=SeverityLevel.MEDIUM,
                    confidence=1.0,
                    title="No Automated CI/CD Workflows Found",
                    description="Repository lacks continuous integration workflows (.github/workflows, .gitlab-ci.yml, etc.) to automate testing on pull requests.",
                    recommendation="Configure GitHub Actions or equivalent CI automation to build and run test suites on commit.",
                    location=FindingLocation(
                        file_path=".github/workflows/", start_line=1, end_line=1
                    ),
                )
            )

        # 4. Unpinned Dependencies or Missing Lockfile Finding
        if has_manifest and (not has_lockfile or unpinned_deps):
            desc = (
                "Repository declares dependencies but lacks a deterministic lockfile (e.g. poetry.lock, package-lock.json)."
                if not has_lockfile
                else f"Repository contains {len(unpinned_deps)} unpinned dependency entries: {', '.join(unpinned_deps[:5])}"
            )
            findings.append(
                NormalizedFinding(
                    analyzer_id="repository-hygiene",
                    tool_version=self.metadata.version,
                    rule_id="RULE-DEP-UNPINNED",
                    category=EvidenceCategory.DEPENDENCY_HEALTH,
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.9,
                    title="Unpinned Dependencies / Missing Deterministic Lockfile",
                    description=desc,
                    recommendation="Pin all direct dependency versions and commit a deterministic lockfile to guarantee reproducible environments.",
                    location=FindingLocation(
                        file_path="requirements.txt", start_line=1, end_line=1
                    ),
                    raw_evidence={"unpinned_packages": unpinned_deps, "has_lockfile": has_lockfile},
                )
            )

        return findings
