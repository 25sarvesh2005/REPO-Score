"""
Snapshot storage management, path traversal defense, resource limit enforcement, and tree hashing.
"""

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
from typing import List, Optional, Tuple

from backend.api.errors import RepoScoreException
from backend.core.config import settings
from backend.repository.models import FileManifestEntry, SnapshotManifest


class SnapshotSecurityError(RepoScoreException):
    """Raised when path traversal or symlink breakout is detected in repository content."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            title="Snapshot Security Violation",
            status_code=400,
            error_type="https://reposcore.internal/errors/path-traversal-detected",
        )
        self.code = "PATH_TRAVERSAL_DETECTED"


class RepositorySizeExceededError(RepoScoreException):
    """Raised when uncompressed repository size exceeds maximum permitted quota."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            title="Repository Size Exceeded",
            status_code=400,
            error_type="https://reposcore.internal/errors/size-exceeded",
        )
        self.code = "SIZE_EXCEEDED"


class RepositoryFileCountExceededError(RepoScoreException):
    """Raised when repository file count exceeds maximum permitted limit."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            title="File Count Exceeded",
            status_code=400,
            error_type="https://reposcore.internal/errors/file-count-exceeded",
        )
        self.code = "FILE_COUNT_EXCEEDED"


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file efficiently using 64KB chunks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_deterministic_tree_hash(entries: List[FileManifestEntry]) -> str:
    """
    Compute a deterministic tree hash from sorted file entries.
    Invariance guarantee: Sorted by canonical POSIX relative path.
    Format: sha256(sum(f"{entry.path}:{entry.size_bytes}:{entry.sha256}\n"))
    """
    sorted_entries = sorted(entries, key=lambda e: e.path)
    tree_hasher = hashlib.sha256()
    for entry in sorted_entries:
        line = f"{entry.path}:{entry.size_bytes}:{entry.sha256}\n"
        tree_hasher.update(line.encode("utf-8"))
    return tree_hasher.hexdigest()


def build_snapshot_manifest(
    snapshot_dir: Path,
    commit_sha: str,
    max_size_bytes: Optional[int] = None,
    max_file_count: Optional[int] = None,
) -> SnapshotManifest:
    """
    Inspect all files in snapshot_dir, enforcing security isolation and resource quotas.
    
    Security controls:
    - Path traversal prevention: ensures all files resolve inside snapshot_dir.
    - Symlink breakout neutralization: skips or rejects symlinks escaping snapshot root.
    - Resource limits: terminates immediately if size or count exceeds limits.
    """
    effective_max_size = max_size_bytes or settings.MAX_REPO_SIZE_BYTES
    effective_max_files = max_file_count or settings.MAX_REPO_FILE_COUNT

    resolved_root = snapshot_dir.resolve()
    entries: List[FileManifestEntry] = []
    total_bytes = 0
    total_files = 0

    for root, dirs, files in os.walk(resolved_root, topdown=True, followlinks=False):
        current_dir = Path(root)

        # Do not traverse into .git internal metadata directories
        if ".git" in dirs:
            dirs.remove(".git")

        # Check directory path resolution
        try:
            resolved_dir = current_dir.resolve()
            if not str(resolved_dir).startswith(str(resolved_root)):
                raise SnapshotSecurityError(
                    f"Directory '{current_dir}' resolves outside snapshot root '{resolved_root}'."
                )
        except (ValueError, RuntimeError) as exc:
            raise SnapshotSecurityError(f"Directory resolution error: {exc}") from exc

        for filename in files:
            file_path = current_dir / filename
            rel_path = file_path.relative_to(resolved_root)
            posix_rel_path = PurePosixPath(rel_path).as_posix()

            # Ignore .git metadata files if any leak through
            if posix_rel_path.startswith(".git/"):
                continue

            # Symlink validation
            is_symlink = file_path.is_symlink()
            if is_symlink:
                try:
                    target_resolved = file_path.resolve()
                    if not str(target_resolved).startswith(str(resolved_root)):
                        # Breakout detected: remove malicious symlink to prevent host escape
                        file_path.unlink()
                        continue
                except Exception:
                    # Broken or circular symlink - remove it
                    file_path.unlink()
                    continue

            # File count quota
            total_files += 1
            if total_files > effective_max_files:
                raise RepositoryFileCountExceededError(
                    f"Repository file count {total_files} exceeds limit of {effective_max_files} files."
                )

            # File size quota
            try:
                stat_result = file_path.stat()
                file_size = stat_result.st_size
            except OSError as exc:
                # File inaccessible or deleted
                continue

            total_bytes += file_size
            if total_bytes > effective_max_size:
                raise RepositorySizeExceededError(
                    f"Repository uncompressed size {total_bytes} bytes exceeds limit of {effective_max_size} bytes."
                )

            file_hash = compute_file_sha256(file_path)
            entries.append(
                FileManifestEntry(
                    path=posix_rel_path,
                    size_bytes=file_size,
                    sha256=file_hash,
                    is_symlink=is_symlink,
                )
            )

    tree_hash = compute_deterministic_tree_hash(entries)

    return SnapshotManifest(
        commit_sha=commit_sha,
        tree_hash=tree_hash,
        total_bytes=total_bytes,
        total_files=total_files,
        files=entries,
    )


def make_directory_read_only(directory: Path) -> None:
    """
    Enforce read-only permissions on a snapshot directory.
    Cross-platform: Strips write permissions on files and directories.
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                current_mode = os.stat(filepath).st_mode
                os.chmod(filepath, current_mode & ~stat.S_IWRITE)
            except OSError:
                pass
        for d in dirs:
            dirpath = os.path.join(root, d)
            try:
                current_mode = os.stat(dirpath).st_mode
                os.chmod(dirpath, current_mode & ~stat.S_IWRITE)
            except OSError:
                pass


def make_directory_writable(directory: Path) -> None:
    """
    Restore write permissions to allow clean deletion during teardown or errors.
    """
    if not directory.exists():
        return
    for root, dirs, files in os.walk(directory, topdown=False):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                current_mode = os.stat(filepath).st_mode
                os.chmod(filepath, current_mode | stat.S_IWRITE)
            except OSError:
                pass
        for d in dirs:
            dirpath = os.path.join(root, d)
            try:
                current_mode = os.stat(dirpath).st_mode
                os.chmod(dirpath, current_mode | stat.S_IWRITE)
            except OSError:
                pass


def safe_remove_directory(directory: Path) -> None:
    """Safely and recursively remove a snapshot directory, handling read-only attributes."""
    if not directory.exists():
        return
    make_directory_writable(directory)
    shutil.rmtree(directory, ignore_errors=True)
