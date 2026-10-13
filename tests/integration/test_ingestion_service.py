"""
Integration tests for RepositoryIngestionService, snapshot deduplication, and failure modes.
"""

from pathlib import Path

import pytest

from backend.repository.ingestion import (
    GitIngestionClient,
    IngestionAuthError,
    IngestionNotFoundError,
    IngestionTimeoutError,
)
from backend.repository.models import EvaluatorCategory, IngestionFailureReason
from backend.repository.service import RepositoryIngestionService


class MockGitIngestionClient(GitIngestionClient):
    """Test git client that simulates cloning without requiring network calls."""

    def __init__(self, commit_sha: str = "a" * 40) -> None:
        super().__init__()
        self.mock_commit_sha = commit_sha
        self.should_fail: str | None = None

    async def clone_repository(
        self,
        canonical_url: str,
        target_dir: Path,
        ref: str | None = None,
    ) -> dict[str, str]:
        if self.should_fail == "timeout":
            raise IngestionTimeoutError("Simulated clone timeout")
        if self.should_fail == "not_found":
            raise IngestionNotFoundError("Simulated repository not found")
        if self.should_fail == "auth":
            raise IngestionAuthError("Simulated private repo auth error")

        # Create mock repository files
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "pyproject.toml").write_text(
            """
[project]
name = "sample-service"
dependencies = ["fastapi", "uvicorn"]
            """,
            encoding="utf-8",
        )
        (target_dir / "main.py").write_text("import fastapi\n", encoding="utf-8")
        dot_git = target_dir / ".git"
        dot_git.mkdir()
        (dot_git / "config").write_text("[core]\n", encoding="utf-8")

        return {
            "commit_sha": self.mock_commit_sha,
            "commit_message": "feat: initial commit",
            "author_name": "RepoScore Agent",
            "commit_date": "2026-10-12T12:00:00Z",
        }


@pytest.fixture
def service_and_mock(tmp_path: Path):
    storage_root = tmp_path / "snapshots"
    mock_git = MockGitIngestionClient(commit_sha="1234567890abcdef1234567890abcdef12345678")
    service = RepositoryIngestionService(storage_root=storage_root, git_client=mock_git)
    return service, mock_git


@pytest.mark.asyncio
async def test_successful_ingestion_and_deduplication(service_and_mock) -> None:
    service, mock_git = service_and_mock
    repo_url = "https://github.com/org/test-api"

    # First ingestion: creates snapshot
    result1 = await service.ingest_repository(repo_url, ref="main")

    assert result1.success is True
    assert result1.resolved_commit_sha == "1234567890abcdef1234567890abcdef12345678"
    assert result1.is_duplicate_snapshot is False
    assert result1.total_files == 2  # pyproject.toml, main.py (dot_git removed)
    assert len(result1.tree_hash) == 64
    assert result1.technologies is not None
    assert result1.technologies.primary_language == "Python"
    assert result1.technologies.evaluator_category == EvaluatorCategory.WEB_API

    # Second ingestion: deduplicates snapshot
    result2 = await service.ingest_repository(repo_url, ref="main")

    assert result2.success is True
    assert result2.is_duplicate_snapshot is True
    assert result2.resolved_commit_sha == result1.resolved_commit_sha
    assert result2.tree_hash == result1.tree_hash
    assert result2.total_files == result1.total_files


@pytest.mark.asyncio
async def test_ingestion_timeout_failure(service_and_mock) -> None:
    service, mock_git = service_and_mock
    mock_git.should_fail = "timeout"

    result = await service.ingest_repository("https://github.com/org/hanging-repo")

    assert result.success is False
    assert result.error_reason == IngestionFailureReason.TIMEOUT
    assert "timeout" in result.error_message.lower()


@pytest.mark.asyncio
async def test_ingestion_not_found_failure(service_and_mock) -> None:
    service, mock_git = service_and_mock
    mock_git.should_fail = "not_found"

    result = await service.ingest_repository("https://github.com/org/missing-repo")

    assert result.success is False
    assert result.error_reason == IngestionFailureReason.REPOSITORY_NOT_FOUND


@pytest.mark.asyncio
async def test_ingestion_auth_failure(service_and_mock) -> None:
    service, mock_git = service_and_mock
    mock_git.should_fail = "auth"

    result = await service.ingest_repository("https://github.com/org/private-repo")

    assert result.success is False
    assert result.error_reason == IngestionFailureReason.AUTH_REQUIRED
