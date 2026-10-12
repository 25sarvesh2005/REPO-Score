"""
Repository ingestion and immutable snapshot subsystem.
"""

from backend.repository.detector import (
    detect_technologies_and_category,
)
from backend.repository.ingestion import (
    GitIngestionClient,
    IngestionAuthError,
    IngestionCorruptGitError,
    IngestionError,
    IngestionNotFoundError,
    IngestionTimeoutError,
)
from backend.repository.models import (
    EvaluatorCategory,
    FileManifestEntry,
    IngestionFailureReason,
    IngestionResult,
    RepositoryReference,
    SnapshotManifest,
    TechnologyDetectionResult,
)
from backend.repository.service import RepositoryIngestionService
from backend.repository.snapshot import (
    RepositoryFileCountExceededError,
    RepositorySizeExceededError,
    SnapshotSecurityError,
    build_snapshot_manifest,
    compute_deterministic_tree_hash,
    compute_file_sha256,
    make_directory_read_only,
    make_directory_writable,
    safe_remove_directory,
)
from backend.repository.validator import (
    InvalidReferenceError,
    InvalidRepositoryUrlError,
    validate_and_parse_repository_url,
    validate_git_ref,
)

__all__ = [
    "EvaluatorCategory",
    "FileManifestEntry",
    "GitIngestionClient",
    "IngestionAuthError",
    "IngestionCorruptGitError",
    "IngestionError",
    "IngestionFailureReason",
    "IngestionNotFoundError",
    "IngestionResult",
    "IngestionTimeoutError",
    "InvalidReferenceError",
    "InvalidRepositoryUrlError",
    "RepositoryFileCountExceededError",
    "RepositoryIngestionService",
    "RepositoryReference",
    "RepositorySizeExceededError",
    "SnapshotManifest",
    "SnapshotSecurityError",
    "TechnologyDetectionResult",
    "build_snapshot_manifest",
    "compute_deterministic_tree_hash",
    "compute_file_sha256",
    "detect_technologies_and_category",
    "make_directory_read_only",
    "make_directory_writable",
    "safe_remove_directory",
    "validate_and_parse_repository_url",
    "validate_git_ref",
]
