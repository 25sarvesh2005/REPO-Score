"""
Unit tests for repository snapshot creation, integrity hashing, quotas, and security.
"""

from pathlib import Path

import pytest

from backend.repository.models import FileManifestEntry
from backend.repository.snapshot import (
    RepositoryFileCountExceededError,
    RepositorySizeExceededError,
    build_snapshot_manifest,
    compute_deterministic_tree_hash,
    compute_file_sha256,
    make_directory_read_only,
    safe_remove_directory,
)


@pytest.fixture
def temp_repo_dir(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Mock Repo\nHello World\n", encoding="utf-8")
    (repo_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    sub_dir = repo_dir / "src"
    sub_dir.mkdir()
    (sub_dir / "utils.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    return repo_dir


def test_compute_file_sha256(temp_repo_dir: Path) -> None:
    readme = temp_repo_dir / "README.md"
    digest = compute_file_sha256(readme)
    assert len(digest) == 64
    assert isinstance(digest, str)


def test_deterministic_tree_hash_order_invariance() -> None:
    entry1 = FileManifestEntry(path="a.py", size_bytes=10, sha256="aaa" * 21 + "a")
    entry2 = FileManifestEntry(path="b.py", size_bytes=20, sha256="bbb" * 21 + "b")

    hash_forward = compute_deterministic_tree_hash([entry1, entry2])
    hash_reversed = compute_deterministic_tree_hash([entry2, entry1])

    assert hash_forward == hash_reversed
    assert len(hash_forward) == 64


def test_build_snapshot_manifest_success(temp_repo_dir: Path) -> None:
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    manifest = build_snapshot_manifest(temp_repo_dir, commit_sha)

    assert manifest.commit_sha == commit_sha
    assert manifest.total_files == 3
    assert manifest.total_bytes > 0
    assert len(manifest.tree_hash) == 64
    assert len(manifest.files) == 3

    paths = [f.path for f in manifest.files]
    assert "README.md" in paths
    assert "main.py" in paths
    assert "src/utils.py" in paths


def test_snapshot_size_quota_exceeded(temp_repo_dir: Path) -> None:
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    # Set limit to 10 bytes so the files trigger size limit
    with pytest.raises(RepositorySizeExceededError):
        build_snapshot_manifest(temp_repo_dir, commit_sha, max_size_bytes=10)


def test_snapshot_file_count_quota_exceeded(temp_repo_dir: Path) -> None:
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    # Set limit to 1 file so 3 files triggers count limit
    with pytest.raises(RepositoryFileCountExceededError):
        build_snapshot_manifest(temp_repo_dir, commit_sha, max_file_count=1)


def test_read_only_protection_and_cleanup(temp_repo_dir: Path) -> None:
    make_directory_read_only(temp_repo_dir)

    # Safe remove should handle read-only directory and files cleanly
    safe_remove_directory(temp_repo_dir)
    assert not temp_repo_dir.exists()
