"""
Static technology detection and operational category classification engine.
Strict adherence: Operates purely through static file inspection; NEVER executes repository code.
"""

import json
import os
import re
import tomllib  # Python 3.11+ standard library
from pathlib import Path

from backend.repository.models import (
    EvaluatorCategory,
    TechnologyDetectionResult,
)

# Supported programming language identifiers and manifest markers
LANGUAGE_MANIFEST_SIGNATURES: dict[str, list[str]] = {
    "Python": [
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "poetry.lock",
        "pdm.lock",
    ],
    "Node.js": [
        "package.json",
        "tsconfig.json",
        "yarn.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "bun.lockb",
    ],
    "Go": ["go.mod", "go.sum"],
    "Rust": ["Cargo.toml", "Cargo.lock"],
    "Java": ["pom.xml", "build.gradle", "build.gradle.kts"],
}

# Framework identifiers and signature dependencies
PYTHON_FRAMEWORK_SIGNATURES: dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "sanic": "Sanic",
    "celery": "Celery",
    "rq": "RQ",
    "click": "Click",
    "typer": "Typer",
    "pytest": "pytest",
    "unittest": "unittest",
}

NODE_FRAMEWORK_SIGNATURES: dict[str, str] = {
    "express": "Express",
    "fastify": "Fastify",
    "next": "Next.js",
    "nest": "NestJS",
    "@nestjs/core": "NestJS",
    "koa": "Koa",
    "bull": "Bull",
    "bullmq": "BullMQ",
    "commander": "Commander",
    "yargs": "Yargs",
    "jest": "Jest",
    "vitest": "Vitest",
    "mocha": "Mocha",
}

WEB_FRAMEWORKS: set[str] = {
    "FastAPI",
    "Flask",
    "Django",
    "Starlette",
    "Tornado",
    "Sanic",
    "Express",
    "Fastify",
    "Next.js",
    "NestJS",
    "Koa",
    "Spring Boot",
    "Gin",
    "Echo",
    "Fiber",
    "Chi",
    "Actix-web",
    "Axum",
    "Rocket",
}

CLI_FRAMEWORKS: set[str] = {"Click", "Typer", "Commander", "Yargs", "Clap", "Cobra"}

WORKER_FRAMEWORKS: set[str] = {"Celery", "RQ", "Bull", "BullMQ"}


def _read_file_text_safe(path: Path, max_bytes: int = 512 * 1024) -> str:
    """Safely read a text file up to max_bytes without executing or parsing foreign scripts."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def detect_python_manifests(
    snapshot_dir: Path,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Statically inspect Python manifests (pyproject.toml, requirements.txt, setup.py).
    Returns (frameworks, package_managers, entrypoints, test_runners).
    """
    frameworks: list[str] = []
    package_managers: list[str] = []
    entrypoints: list[str] = []
    test_runners: list[str] = []

    # Check pyproject.toml
    pyproject_path = snapshot_dir / "pyproject.toml"
    if pyproject_path.exists():
        content = _read_file_text_safe(pyproject_path)
        try:
            parsed = tomllib.loads(content)
            # Package manager / build tool
            build_system = parsed.get("build-system", {}).get("build-backend", "")
            if "poetry" in build_system:
                package_managers.append("poetry")
            elif "flit" in build_system:
                package_managers.append("flit")
            elif "pdm" in build_system:
                package_managers.append("pdm")
            elif "hatch" in build_system:
                package_managers.append("hatch")
            else:
                package_managers.append("pip")

            # Dependencies
            dependencies = parsed.get("project", {}).get("dependencies", [])
            poetry_deps = parsed.get("tool", {}).get("poetry", {}).get("dependencies", {})
            if isinstance(poetry_deps, dict):
                dependencies.extend(poetry_deps.keys())

            dep_str = " ".join([str(d).lower() for d in dependencies])
            for sig, name in PYTHON_FRAMEWORK_SIGNATURES.items():
                if sig in dep_str and name not in frameworks:
                    if sig in {"pytest", "unittest"}:
                        test_runners.append(name)
                    else:
                        frameworks.append(name)

            # CLI Scripts
            scripts = parsed.get("project", {}).get("scripts", {})
            for script_name in scripts:
                entrypoints.append(f"cli:{script_name}")

        except Exception:
            package_managers.append("pip")

    # Check requirements.txt
    req_path = snapshot_dir / "requirements.txt"
    if req_path.exists():
        package_managers.append("pip")
        content = _read_file_text_safe(req_path).lower()
        for sig, name in PYTHON_FRAMEWORK_SIGNATURES.items():
            if re.search(rf"\b{re.escape(sig)}\b", content) and name not in frameworks:
                if sig in {"pytest", "unittest"}:
                    test_runners.append(name)
                else:
                    frameworks.append(name)

    # Check common entrypoint files
    for candidate in ["main.py", "app.py", "run.py", "cli.py", "server.py", "manage.py"]:
        if (snapshot_dir / candidate).exists():
            entrypoints.append(candidate)

    # Check tests directory
    if (snapshot_dir / "tests").exists() or (snapshot_dir / "test").exists():
        if "pytest" not in test_runners:
            test_runners.append("pytest")

    return frameworks, package_managers, entrypoints, test_runners


def detect_node_manifests(snapshot_dir: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Statically inspect Node.js manifests (package.json, lockfiles).
    Returns (frameworks, package_managers, entrypoints, test_runners).
    """
    frameworks: list[str] = []
    package_managers: list[str] = []
    entrypoints: list[str] = []
    test_runners: list[str] = []

    # Check lockfiles for package manager
    if (snapshot_dir / "pnpm-lock.yaml").exists():
        package_managers.append("pnpm")
    elif (snapshot_dir / "yarn.lock").exists():
        package_managers.append("yarn")
    elif (snapshot_dir / "bun.lockb").exists():
        package_managers.append("bun")
    elif (snapshot_dir / "package-lock.json").exists():
        package_managers.append("npm")

    pkg_path = snapshot_dir / "package.json"
    if pkg_path.exists():
        content = _read_file_text_safe(pkg_path)
        try:
            parsed = json.loads(content)
            deps = parsed.get("dependencies", {})
            dev_deps = parsed.get("devDependencies", {})
            all_deps = {**deps, **dev_deps}
            all_keys = [k.lower() for k in all_deps]

            for sig, name in NODE_FRAMEWORK_SIGNATURES.items():
                if any(sig in k for k in all_keys) and name not in frameworks:
                    if sig in {"jest", "vitest", "mocha"}:
                        test_runners.append(name)
                    else:
                        frameworks.append(name)

            # Entrypoints from package.json
            if parsed.get("main"):
                entrypoints.append(str(parsed["main"]))
            if parsed.get("scripts", {}).get("start"):
                entrypoints.append(f"npm-start:{parsed['scripts']['start']}")
            if parsed.get("bin"):
                entrypoints.append("package.json:bin")

            if not package_managers:
                package_managers.append("npm")

        except Exception:
            if not package_managers:
                package_managers.append("npm")

    # Common entrypoint candidate files
    for candidate in [
        "index.js",
        "index.ts",
        "server.js",
        "server.ts",
        "src/index.ts",
        "src/index.js",
    ]:
        if (snapshot_dir / candidate).exists() and candidate not in entrypoints:
            entrypoints.append(candidate)

    return frameworks, package_managers, entrypoints, test_runners


def detect_ci_cd(snapshot_dir: Path) -> list[str]:
    """Identify CI/CD pipelines statically from repository configuration files."""
    ci_cd: list[str] = []
    # GitHub Actions
    gh_workflows = snapshot_dir / ".github" / "workflows"
    if gh_workflows.exists() and gh_workflows.is_dir():
        try:
            workflow_files = [f for f in os.listdir(gh_workflows) if f.endswith((".yml", ".yaml"))]
            if workflow_files:
                ci_cd.append("GitHub Actions")
        except OSError:
            pass

    # GitLab CI
    if (snapshot_dir / ".gitlab-ci.yml").exists():
        ci_cd.append("GitLab CI")

    # Jenkins
    if (snapshot_dir / "Jenkinsfile").exists():
        ci_cd.append("Jenkins")

    # CircleCI
    if (snapshot_dir / ".circleci" / "config.yml").exists():
        ci_cd.append("CircleCI")

    return ci_cd


def detect_technologies_and_category(snapshot_dir: Path) -> TechnologyDetectionResult:
    """
    Main detection entrypoint: Deterministically identifies language, frameworks,
    entrypoints, package managers, and operational category without running user code.
    """
    resolved_dir = snapshot_dir.resolve()
    detected_languages: dict[str, float] = {}
    detected_frameworks: list[str] = []
    detected_package_managers: list[str] = []
    detected_entrypoints: list[str] = []
    detected_test_runners: list[str] = []

    # 1. Detect Languages based on manifests in root and primary subdirectories
    search_dirs: list[Path] = [resolved_dir]
    try:
        for child in resolved_dir.iterdir():
            if (
                child.is_dir()
                and not child.name.startswith(".")
                and child.name
                not in {
                    "node_modules",
                    "venv",
                    ".venv",
                    ".git",
                    "dist",
                    "build",
                    "target",
                    "__pycache__",
                }
            ):
                search_dirs.append(child)
    except Exception:
        pass

    for s_dir in search_dirs:
        for language, manifest_files in LANGUAGE_MANIFEST_SIGNATURES.items():
            found_manifests = [m for m in manifest_files if (s_dir / m).exists()]
            if found_manifests:
                detected_languages[language] = 1.0

    # Fallback to source file extensions if no manifest found
    if not detected_languages:
        ext_map = {
            ".py": "Python",
            ".js": "Node.js",
            ".ts": "Node.js",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
        }
        for _root, dirs, files in os.walk(resolved_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in {"node_modules", "venv", ".venv"}
            ]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in ext_map:
                    detected_languages[ext_map[ext]] = 0.8
            if detected_languages:
                break

    # 2. Extract Frameworks, Entrypoints, and Tooling across search directories
    for s_dir in search_dirs:
        rel_prefix = f"{s_dir.name}/" if s_dir != resolved_dir else ""
        if "Python" in detected_languages:
            py_fw, py_pm, py_ep, py_tr = detect_python_manifests(s_dir)
            detected_frameworks.extend(py_fw)
            detected_package_managers.extend(py_pm)
            detected_entrypoints.extend(
                [f"{rel_prefix}{ep}" if not ep.startswith("cli:") else ep for ep in py_ep]
            )
            detected_test_runners.extend(py_tr)

        if "Node.js" in detected_languages:
            node_fw, node_pm, node_ep, node_tr = detect_node_manifests(s_dir)
            detected_frameworks.extend(node_fw)
            detected_package_managers.extend(node_pm)
            detected_entrypoints.extend(
                [f"{rel_prefix}{ep}" if not ep.startswith("cli:") else ep for ep in node_ep]
            )
            detected_test_runners.extend(node_tr)

        if "Go" in detected_languages:
            detected_package_managers.append("go modules")
            detected_test_runners.append("go test")
            if (s_dir / "main.go").exists():
                detected_entrypoints.append(f"{rel_prefix}main.go")

        if "Rust" in detected_languages:
            detected_package_managers.append("cargo")
            detected_test_runners.append("cargo test")
            if (s_dir / "src" / "main.rs").exists():
                detected_entrypoints.append(f"{rel_prefix}src/main.rs")

    # Deduplicate lists preserving order
    detected_frameworks = list(dict.fromkeys(detected_frameworks))
    detected_package_managers = list(dict.fromkeys(detected_package_managers))
    detected_entrypoints = list(dict.fromkeys(detected_entrypoints))
    detected_test_runners = list(dict.fromkeys(detected_test_runners))

    # CI/CD
    detected_ci_cd = detect_ci_cd(resolved_dir)

    # 3. Primary Language
    primary_language: str | None = None
    if detected_languages:
        # Prioritize language with web/worker framework if multiple exist
        if "Python" in detected_languages and any(
            f in {"FastAPI", "Flask", "Django"} for f in detected_frameworks
        ):
            primary_language = "Python"
        elif "Node.js" in detected_languages and any(
            f in {"Express", "NestJS", "Fastify", "Next.js"} for f in detected_frameworks
        ):
            primary_language = "Node.js"
        else:
            primary_language = max(detected_languages.keys(), key=lambda k: detected_languages[k])

    # 4. Classify Operational Category
    category = EvaluatorCategory.UNSUPPORTED
    confidence = 0.0

    if not detected_languages:
        category = EvaluatorCategory.UNSUPPORTED
        confidence = 0.0
    elif any(f in WEB_FRAMEWORKS for f in detected_frameworks):
        category = EvaluatorCategory.WEB_API
        confidence = 0.95
    elif any(f in WORKER_FRAMEWORKS for f in detected_frameworks):
        category = EvaluatorCategory.BACKGROUND_WORKER
        confidence = 0.90
    elif any(f in CLI_FRAMEWORKS for f in detected_frameworks) or any(
        "cli:" in ep for ep in detected_entrypoints
    ):
        category = EvaluatorCategory.CLI_TOOL
        confidence = 0.90
    elif detected_entrypoints and any(
        ep.endswith(("main.py", "app.py", "index.js", "index.ts", "main.go", "src/main.rs"))
        for ep in detected_entrypoints
    ):
        # Has an executable entrypoint but no explicit web framework -> default to CLI or daemon
        category = EvaluatorCategory.CLI_TOOL
        confidence = 0.75
    elif detected_languages:
        # Recognized library repository
        category = EvaluatorCategory.LIBRARY
        confidence = 0.85

    return TechnologyDetectionResult(
        primary_language=primary_language,
        detected_languages=detected_languages,
        detected_frameworks=detected_frameworks,
        detected_package_managers=detected_package_managers,
        detected_entrypoints=detected_entrypoints,
        detected_test_runners=detected_test_runners,
        detected_ci_cd=detected_ci_cd,
        evaluator_category=category,
        confidence_score=confidence,
    )
