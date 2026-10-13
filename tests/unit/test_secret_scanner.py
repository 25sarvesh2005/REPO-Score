"""
Unit tests for cryptographic secret and credential scanner adapter.
"""

from pathlib import Path

import pytest

from backend.analyzers.secret_scanner import SecretScannerAnalyzer
from backend.api.schemas.contracts import SeverityLevel


@pytest.fixture
def scanner() -> SecretScannerAnalyzer:
    return SecretScannerAnalyzer()


@pytest.mark.asyncio
async def test_detect_hardcoded_github_token(
    tmp_path: Path, scanner: SecretScannerAnalyzer
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.py").write_text(
        'GITHUB_API_KEY = "ghp_111122223333444455556666777788889999"\n',
        encoding="utf-8",
    )

    result = await scanner.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.rule_id == "SEC-001-GITHUB-TOKEN"
    assert f.severity == SeverityLevel.CRITICAL
    assert "CWE-798" in f.cwe_ids
    # Snippet must not show the full token in plaintext
    assert "ghp_111122223333444455556666777788889999" not in f.location.snippet
    assert "ghp_" in f.location.snippet


@pytest.mark.asyncio
async def test_detect_hardcoded_aws_key(tmp_path: Path, scanner: SecretScannerAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "aws.py").write_text(
        'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n',
        encoding="utf-8",
    )

    result = await scanner.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "SEC-002-AWS-KEY"
    assert result.findings[0].severity == SeverityLevel.CRITICAL


@pytest.mark.asyncio
async def test_detect_database_credentials(tmp_path: Path, scanner: SecretScannerAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "db.py").write_text(
        'DATABASE_URL = "postgres://dbadmin:p@ssword123@db.internal:5432/app"\n',
        encoding="utf-8",
    )

    result = await scanner.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "SEC-004-DATABASE-URI"
    assert result.findings[0].severity == SeverityLevel.HIGH


@pytest.mark.asyncio
async def test_clean_files_zero_secret_findings(
    tmp_path: Path, scanner: SecretScannerAnalyzer
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "clean.py").write_text(
        'import os\nTOKEN = os.environ.get("TOKEN")\n',
        encoding="utf-8",
    )

    result = await scanner.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 0
