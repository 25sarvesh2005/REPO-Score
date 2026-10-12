"""
Unit tests for dependency vulnerability scanner adapter.
"""

from pathlib import Path
import pytest

from backend.analyzers.dependency_scanner import DependencyVulnerabilityAnalyzer
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


@pytest.fixture
def dep_analyzer() -> DependencyVulnerabilityAnalyzer:
    return DependencyVulnerabilityAnalyzer()


@pytest.mark.asyncio
async def test_detect_vulnerable_python_dependency(tmp_path: Path, dep_analyzer: DependencyVulnerabilityAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text(
        "requests==2.28.1\nurllib3==1.26.15\nclick>=8.0.0\n",
        encoding="utf-8",
    )

    result = await dep_analyzer.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 2

    cves = [f.rule_id for f in result.findings]
    assert "CVE-2023-32681" in cves  # requests
    assert "CVE-2023-45803" in cves  # urllib3

    f = next(f for f in result.findings if f.rule_id == "CVE-2023-32681")
    assert f.category == EvidenceCategory.DEPENDENCY_HEALTH
    assert "Upgrade 'requests'" in f.recommendation


@pytest.mark.asyncio
async def test_detect_vulnerable_node_dependency(tmp_path: Path, dep_analyzer: DependencyVulnerabilityAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        """
{
  "name": "vulnerable-app",
  "dependencies": {
    "lodash": "^4.17.19"
  }
}
        """,
        encoding="utf-8",
    )

    result = await dep_analyzer.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "CVE-2021-23337"
    assert result.findings[0].severity == SeverityLevel.HIGH


@pytest.mark.asyncio
async def test_safe_dependencies_zero_findings(tmp_path: Path, dep_analyzer: DependencyVulnerabilityAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text(
        "requests==2.32.3\nurllib3==2.2.2\n",
        encoding="utf-8",
    )

    result = await dep_analyzer.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 0


@pytest.mark.asyncio
async def test_malformed_requirements_handled_gracefully(tmp_path: Path, dep_analyzer: DependencyVulnerabilityAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text(
        "invalid!syntax???==not-a-version\n",
        encoding="utf-8",
    )

    result = await dep_analyzer.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 0
