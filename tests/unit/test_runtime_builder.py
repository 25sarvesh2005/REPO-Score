"""
Unit tests for build strategy resolution and sandboxed execution.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.repository.models import TechnologyDetectionResult
from backend.runtime.builder import (
    categorize_build_error,
    execute_build,
    resolve_build_command,
)
from backend.sandbox.models import SandboxExecutionResult


def test_resolve_build_command_python(tmp_path: Path):
    # requirements.txt
    (tmp_path / "requirements.txt").write_text("fastapi==0.100.0\n")
    det = TechnologyDetectionResult(primary_language="Python")
    cmd = resolve_build_command(tmp_path, det)
    assert cmd == ["pip", "install", "--no-cache-dir", "-r", "requirements.txt"]

    # pyproject.toml with poetry
    tmp_path2 = tmp_path / "poetry_proj"
    tmp_path2.mkdir()
    (tmp_path2 / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")
    (tmp_path2 / "poetry.lock").write_text("")
    det2 = TechnologyDetectionResult(
        primary_language="Python", detected_package_managers=["poetry"]
    )
    cmd2 = resolve_build_command(tmp_path2, det2)
    assert cmd2 == ["poetry", "install", "--no-root"]


def test_resolve_build_command_node_enforces_ignore_scripts(tmp_path: Path):
    # package.json
    (tmp_path / "package.json").write_text('{"name": "test"}')
    det = TechnologyDetectionResult(primary_language="Node.js")
    cmd = resolve_build_command(tmp_path, det)
    assert cmd == ["npm", "install", "--ignore-scripts"]

    # package-lock.json -> npm ci --ignore-scripts
    (tmp_path / "package-lock.json").write_text("{}")
    cmd_ci = resolve_build_command(tmp_path, det)
    assert cmd_ci == ["npm", "ci", "--ignore-scripts"]

    # yarn.lock
    (tmp_path / "yarn.lock").write_text("")
    cmd_yarn = resolve_build_command(tmp_path, det)
    assert cmd_yarn == ["yarn", "install", "--ignore-scripts"]


def test_resolve_build_command_go_and_rust(tmp_path: Path):
    go_dir = tmp_path / "go_proj"
    go_dir.mkdir()
    (go_dir / "go.mod").write_text("module example.com/test\n")
    det_go = TechnologyDetectionResult(primary_language="Go")
    assert resolve_build_command(go_dir, det_go) == ["go", "build", "./..."]

    rust_dir = tmp_path / "rust_proj"
    rust_dir.mkdir()
    (rust_dir / "Cargo.toml").write_text("[package]\nname = 'test'\n")
    det_rust = TechnologyDetectionResult(primary_language="Rust")
    assert resolve_build_command(rust_dir, det_rust) == ["cargo", "build"]


def test_categorize_build_error():
    cat, msg = categorize_build_error("", "No matching distribution found for foo==9.9", 1)
    assert cat == "MISSING_DEPENDENCY"

    cat, msg = categorize_build_error("", "SyntaxError: invalid syntax", 1)
    assert cat == "SYNTAX_ERROR"

    cat, msg = categorize_build_error("", "npm ERR! 404 Not Found", 1)
    assert cat == "NPM_PACKAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_execute_build_success(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    det = TechnologyDetectionResult(primary_language="Python")
    sbx = AsyncMock()
    sbx.execute = AsyncMock(
        return_value=SandboxExecutionResult(exit_code=0, stdout="build ok", stderr="")
    )

    result = await execute_build(sbx, tmp_path, det)
    assert result.success is True
    assert result.exit_code == 0
    assert result.command == ["pip", "install", "--no-cache-dir", "-r", "requirements.txt"]


@pytest.mark.asyncio
async def test_execute_build_noop_for_unmanifested(tmp_path: Path):
    det = TechnologyDetectionResult(primary_language=None)
    sbx = AsyncMock()

    result = await execute_build(sbx, tmp_path, det)
    assert result.success is True
    assert result.artifacts["build_type"] == "NOOP"


@pytest.mark.asyncio
async def test_execute_build_failure(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("badpackage\n")
    det = TechnologyDetectionResult(primary_language="Python")

    def failing_handler(cmd, *args, **kwargs):
        return SandboxExecutionResult(
            exit_code=1,
            stdout="",
            stderr="No matching distribution found for badpackage",
            duration_ms=100,
        )

    sbx = AsyncMock()
    sbx.execute = AsyncMock(side_effect=failing_handler)
    result = await execute_build(sbx, tmp_path, det)
    assert result.success is False
    assert result.exit_code == 1
    assert result.artifacts["error_category"] == "MISSING_DEPENDENCY"
