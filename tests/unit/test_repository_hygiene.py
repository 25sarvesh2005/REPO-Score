"""
Unit tests for RepositoryHygieneAnalyzer.
Verifies empirical detection of missing README, test suites, CI/CD workflows, and lockfiles.
"""

from pathlib import Path

import pytest

from backend.analyzers.repository_hygiene import RepositoryHygieneAnalyzer
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


@pytest.mark.asyncio
async def test_hygiene_clean_repository(tmp_path: Path):
    # Setup clean repo structure
    (tmp_path / "README.md").write_text(
        "# Project Title\nComprehensive guide and overview of project.", encoding="utf-8"
    )
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.111.1\nuvicorn==0.30.0\n", encoding="utf-8"
    )
    (tmp_path / "poetry.lock").write_text("# lockfile content\n", encoding="utf-8")

    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text("name: CI\non: [push]\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    analyzer = RepositoryHygieneAnalyzer()
    assert analyzer.can_analyze({}) is True

    findings = await analyzer._execute_analysis(tmp_path)
    assert len(findings) == 0


@pytest.mark.asyncio
async def test_hygiene_missing_fundamentals(tmp_path: Path):
    # Completely empty repository directory
    analyzer = RepositoryHygieneAnalyzer()
    findings = await analyzer._execute_analysis(tmp_path)

    rule_ids = {f.rule_id for f in findings}
    assert "RULE-DOC-MISSING-README" in rule_ids
    assert "RULE-TEST-NO-TEST-FILES" in rule_ids
    assert "RULE-ENG-NO-CI-WORKFLOW" in rule_ids

    # Verify severity and categories
    doc_finding = next(f for f in findings if f.rule_id == "RULE-DOC-MISSING-README")
    assert doc_finding.category == EvidenceCategory.DOCUMENTATION
    assert doc_finding.severity == SeverityLevel.HIGH

    test_finding = next(f for f in findings if f.rule_id == "RULE-TEST-NO-TEST-FILES")
    assert test_finding.category == EvidenceCategory.TESTING
    assert test_finding.severity == SeverityLevel.HIGH

    ci_finding = next(f for f in findings if f.rule_id == "RULE-ENG-NO-CI-WORKFLOW")
    assert ci_finding.category == EvidenceCategory.ENGINEERING_MATURITY
    assert ci_finding.severity == SeverityLevel.MEDIUM


@pytest.mark.asyncio
async def test_hygiene_unpinned_dependencies(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        "# Title\nComprehensive documentation content...", encoding="utf-8"
    )
    (tmp_path / "requirements.txt").write_text("requests\nflask>=2.0\n", encoding="utf-8")

    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text("name: CI\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_dummy(): pass\n", encoding="utf-8")

    analyzer = RepositoryHygieneAnalyzer()
    findings = await analyzer._execute_analysis(tmp_path)

    rule_ids = {f.rule_id for f in findings}
    assert "RULE-DEP-UNPINNED" in rule_ids
    dep_finding = next(f for f in findings if f.rule_id == "RULE-DEP-UNPINNED")
    assert dep_finding.category == EvidenceCategory.DEPENDENCY_HEALTH
    assert dep_finding.severity == SeverityLevel.MEDIUM
