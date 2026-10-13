"""
Unit tests for static technology detection and application category classification.
"""

from pathlib import Path

from backend.repository.detector import detect_technologies_and_category
from backend.repository.models import EvaluatorCategory


def test_detect_python_fastapi_web_api(tmp_path: Path) -> None:
    repo = tmp_path / "fastapi_app"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        """
[project]
name = "my-service"
version = "0.1.0"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0"
]
        """,
        encoding="utf-8",
    )
    (repo / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )

    # Add CI/CD workflow
    workflows_dir = repo / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text("name: CI\non: push\njobs: {}", encoding="utf-8")

    result = detect_technologies_and_category(repo)

    assert result.primary_language == "Python"
    assert "Python" in result.detected_languages
    assert "FastAPI" in result.detected_frameworks
    assert "main.py" in result.detected_entrypoints
    assert "GitHub Actions" in result.detected_ci_cd
    assert result.evaluator_category == EvaluatorCategory.WEB_API
    assert result.confidence_score >= 0.90


def test_detect_python_cli_tool(tmp_path: Path) -> None:
    repo = tmp_path / "cli_tool"
    repo.mkdir()
    (repo / "requirements.txt").write_text("click>=8.0.0\npytest>=7.0.0\n", encoding="utf-8")
    (repo / "cli.py").write_text("import click\n", encoding="utf-8")

    result = detect_technologies_and_category(repo)

    assert result.primary_language == "Python"
    assert "Click" in result.detected_frameworks
    assert "pytest" in result.detected_test_runners
    assert result.evaluator_category == EvaluatorCategory.CLI_TOOL
    assert result.confidence_score >= 0.85


def test_detect_node_express_web_api(tmp_path: Path) -> None:
    repo = tmp_path / "express_app"
    repo.mkdir()
    (repo / "package.json").write_text(
        """
{
  "name": "api-service",
  "version": "1.0.0",
  "main": "server.js",
  "dependencies": {
    "express": "^4.18.2"
  },
  "devDependencies": {
    "jest": "^29.5.0"
  }
}
        """,
        encoding="utf-8",
    )
    (repo / "server.js").write_text("const express = require('express');\n", encoding="utf-8")
    (repo / "package-lock.json").write_text("{}", encoding="utf-8")

    result = detect_technologies_and_category(repo)

    assert result.primary_language == "Node.js"
    assert "Express" in result.detected_frameworks
    assert "server.js" in result.detected_entrypoints
    assert "Jest" in result.detected_test_runners
    assert "npm" in result.detected_package_managers
    assert result.evaluator_category == EvaluatorCategory.WEB_API
    assert result.confidence_score >= 0.90


def test_detect_python_worker(tmp_path: Path) -> None:
    repo = tmp_path / "celery_worker"
    repo.mkdir()
    (repo / "requirements.txt").write_text("celery>=5.3.0\nredis>=4.5.0\n", encoding="utf-8")

    result = detect_technologies_and_category(repo)

    assert result.primary_language == "Python"
    assert "Celery" in result.detected_frameworks
    assert result.evaluator_category == EvaluatorCategory.BACKGROUND_WORKER


def test_detect_python_library(tmp_path: Path) -> None:
    repo = tmp_path / "math_lib"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        """
[project]
name = "mathlib"
version = "0.1.0"
dependencies = []
        """,
        encoding="utf-8",
    )

    result = detect_technologies_and_category(repo)

    assert result.primary_language == "Python"
    assert result.evaluator_category == EvaluatorCategory.LIBRARY


def test_detect_unsupported_repo(tmp_path: Path) -> None:
    repo = tmp_path / "empty_docs"
    repo.mkdir()
    (repo / "README.txt").write_text("Plain text documentation without code.", encoding="utf-8")

    result = detect_technologies_and_category(repo)

    assert result.primary_language is None
    assert result.evaluator_category == EvaluatorCategory.UNSUPPORTED
    assert result.confidence_score == 0.0
