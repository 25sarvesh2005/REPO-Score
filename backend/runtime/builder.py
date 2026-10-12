"""
Build Strategy Resolution and Sandboxed Compilation Engine.
Adheres strictly to EVAL-021, EVAL-022, EVAL-023, and EVAL-024.
Untrusted build commands execute EXCLUSIVELY inside the isolated sandbox.
"""

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from backend.repository.models import TechnologyDetectionResult
from backend.runtime.models import BuildResult
from backend.sandbox.interface import ISandbox


def resolve_build_command(snapshot_path: Path, detection: TechnologyDetectionResult) -> Optional[List[str]]:
    """
    Deterministically resolve the safe package installation and compilation command
    based on static file detection. Enforces EVAL-022 security script neutralization.
    """
    primary = detection.primary_language or ""

    # 1. Python Build Strategy
    if primary == "Python" or "Python" in detection.detected_languages:
        if (snapshot_path / "requirements.txt").exists():
            return ["pip", "install", "--no-cache-dir", "-r", "requirements.txt"]
        if (snapshot_path / "poetry.lock").exists() or (
            (snapshot_path / "pyproject.toml").exists() and "poetry" in detection.detected_package_managers
        ):
            return ["poetry", "install", "--no-root"]
        if (snapshot_path / "pyproject.toml").exists():
            return ["pip", "install", "--no-cache-dir", "-e", "."]
        if (snapshot_path / "setup.py").exists() or (snapshot_path / "setup.cfg").exists():
            return ["pip", "install", "--no-cache-dir", "-e", "."]
        if (snapshot_path / "Pipfile").exists():
            return ["pipenv", "install", "--deploy"]

    # 2. Node.js Build Strategy (EVAL-022: Enforce --ignore-scripts)
    if primary == "Node.js" or "Node.js" in detection.detected_languages:
        if (snapshot_path / "pnpm-lock.yaml").exists():
            return ["pnpm", "install", "--ignore-scripts"]
        if (snapshot_path / "yarn.lock").exists():
            return ["yarn", "install", "--ignore-scripts"]
        if (snapshot_path / "package-lock.json").exists():
            return ["npm", "ci", "--ignore-scripts"]
        if (snapshot_path / "package.json").exists():
            return ["npm", "install", "--ignore-scripts"]

    # 3. Go Build Strategy
    if primary == "Go" or "Go" in detection.detected_languages:
        if (snapshot_path / "go.mod").exists():
            return ["go", "build", "./..."]

    # 4. Rust Build Strategy
    if primary == "Rust" or "Rust" in detection.detected_languages:
        if (snapshot_path / "Cargo.toml").exists():
            return ["cargo", "build"]

    # 5. Java Build Strategy
    if primary == "Java" or "Java" in detection.detected_languages:
        if (snapshot_path / "pom.xml").exists():
            return ["mvn", "compile", "-DskipTests"]
        if (snapshot_path / "build.gradle").exists() or (snapshot_path / "build.gradle.kts").exists():
            gradle_cmd = "./gradlew" if (snapshot_path / "gradlew").exists() else "gradle"
            return [gradle_cmd, "classes", "-x", "test"]

    return None


def categorize_build_error(stdout: str, stderr: str, exit_code: int) -> Tuple[str, Optional[str]]:
    """
    Categorize compiler or dependency installation errors for diagnostic reporting (EVAL-024).
    Returns (error_category, snippet).
    """
    combined = f"{stdout}\n{stderr}"

    if "No matching distribution found" in combined or "Could not find a version that satisfies" in combined:
        return "MISSING_DEPENDENCY", "Unresolvable dependency or package version conflict."
    if "ModuleNotFoundError" in combined or "ImportError" in combined:
        return "MISSING_MODULE", "Required module not found during build."
    if "SyntaxError" in combined:
        return "SYNTAX_ERROR", "Syntax error encountered during compilation."
    if "npm ERR! 404" in combined or "npm ERR! code E404" in combined:
        return "NPM_PACKAGE_NOT_FOUND", "Node.js package not found in registry."
    if "npm ERR!" in combined:
        return "NPM_BUILD_ERROR", "npm dependency installation failed."
    if "cannot find package" in combined or "go: missing" in combined:
        return "GO_PACKAGE_NOT_FOUND", "Go package or module requirement missing."
    if "error[E0" in combined or "could not compile" in combined:
        return "RUST_COMPILATION_ERROR", "Rust compiler error encountered."
    if "BUILD FAILURE" in combined or "Compilation failure" in combined:
        return "JAVA_COMPILATION_ERROR", "Java Maven/Gradle compilation failure."

    return "GENERIC_BUILD_FAILURE", f"Process exited with non-zero code {exit_code}."


async def execute_build(
    sandbox: ISandbox,
    snapshot_path: Path,
    detection: TechnologyDetectionResult,
    timeout_seconds: int = 300,
) -> BuildResult:
    """
    Execute sandboxed build and dependency resolution adhering to EVAL-021 through EVAL-024.
    """
    command = resolve_build_command(snapshot_path, detection)

    # If repository requires no compilation or package installation
    if not command:
        return BuildResult(
            success=True,
            duration_ms=0,
            exit_code=0,
            stdout="No automated build or package installation required for repository.",
            stderr="",
            command=[],
            timed_out=False,
            oom_killed=False,
            artifacts={"build_type": "NOOP"},
        )

    # Execute build command inside the quarantined container
    exec_result = await sandbox.execute(command, timeout_seconds=timeout_seconds)

    success = (exec_result.exit_code == 0) and (not exec_result.timed_out) and (not exec_result.oom_killed)

    artifacts: Dict[str, Any] = {
        "build_command": command,
        "timed_out": exec_result.timed_out,
        "oom_killed": exec_result.oom_killed,
        "output_truncated": exec_result.output_truncated,
    }

    if not success:
        err_cat, err_hint = categorize_build_error(exec_result.stdout, exec_result.stderr, exec_result.exit_code)
        artifacts["error_category"] = err_cat
        artifacts["error_diagnostic"] = err_hint

    return BuildResult(
        success=success,
        duration_ms=exec_result.duration_ms,
        exit_code=exec_result.exit_code,
        stdout=exec_result.stdout,
        stderr=exec_result.stderr,
        command=command,
        timed_out=exec_result.timed_out,
        oom_killed=exec_result.oom_killed,
        artifacts=artifacts,
    )
