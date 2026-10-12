"""
Domain models and schema definitions for repository ingestion and snapshot management.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluatorCategory(str, Enum):
    """Categorization of application architecture for targeted runtime evaluation."""
    WEB_API = "WEB_API"
    CLI_TOOL = "CLI_TOOL"
    LIBRARY = "LIBRARY"
    BACKGROUND_WORKER = "BACKGROUND_WORKER"
    UNSUPPORTED = "UNSUPPORTED"


class IngestionFailureReason(str, Enum):
    """Structured failure categories for repository ingestion."""
    INVALID_URL = "INVALID_URL"
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    SIZE_EXCEEDED = "SIZE_EXCEEDED"
    FILE_COUNT_EXCEEDED = "FILE_COUNT_EXCEEDED"
    PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"
    CORRUPT_GIT_OBJECTS = "CORRUPT_GIT_OBJECTS"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class RepositoryReference(BaseModel):
    """Parsed and validated repository reference."""
    owner: str = Field(..., description="Repository owner or organization")
    name: str = Field(..., description="Repository name")
    canonical_url: str = Field(..., description="Standard HTTPS repository clone URL")
    ref: Optional[str] = Field(default=None, description="Explicit branch, tag, or commit SHA")
    is_shorthand: bool = Field(default=False, description="Whether reference was provided in shorthand format")


class FileManifestEntry(BaseModel):
    """Integrity record for an individual snapshot file."""
    path: str = Field(..., description="Relative POSIX path from snapshot root")
    size_bytes: int = Field(..., description="File size in bytes")
    sha256: str = Field(..., description="Cryptographic SHA-256 digest of file contents")
    is_symlink: bool = Field(default=False, description="Whether the file entry is a symlink")


class SnapshotManifest(BaseModel):
    """Tamper-evident snapshot manifest containing file metadata and overall tree hash."""
    commit_sha: str = Field(..., min_length=40, max_length=40, description="Full 40-character Git commit SHA")
    tree_hash: str = Field(..., min_length=64, max_length=64, description="Deterministic SHA-256 tree hash")
    total_bytes: int = Field(..., description="Aggregated uncompressed byte size")
    total_files: int = Field(..., description="Total file count across snapshot")
    files: List[FileManifestEntry] = Field(default_factory=list, description="Sorted list of file entries")


class TechnologyDetectionResult(BaseModel):
    """Empirical static detection result derived without executing repository code."""
    primary_language: Optional[str] = Field(default=None, description="Inferred primary programming language")
    detected_languages: Dict[str, float] = Field(
        default_factory=dict, description="Detected languages mapped to confidence score"
    )
    detected_frameworks: List[str] = Field(
        default_factory=list, description="Identified application and web frameworks"
    )
    detected_package_managers: List[str] = Field(
        default_factory=list, description="Identified package managers and lockfile formats"
    )
    detected_entrypoints: List[str] = Field(
        default_factory=list, description="Identified candidate application entrypoints"
    )
    detected_test_runners: List[str] = Field(
        default_factory=list, description="Identified test frameworks and runners"
    )
    detected_ci_cd: List[str] = Field(
        default_factory=list, description="Identified continuous integration workflow configurations"
    )
    evaluator_category: EvaluatorCategory = Field(
        default=EvaluatorCategory.UNSUPPORTED, description="Operational application category"
    )
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Aggregate confidence score for categorization"
    )


class IngestionResult(BaseModel):
    """Complete result of repository ingestion and snapshot creation."""
    success: bool = Field(..., description="Whether ingestion completed successfully")
    repository_url: str = Field(..., description="Original requested repository URL")
    resolved_commit_sha: Optional[str] = Field(default=None, description="Resolved 40-character commit SHA")
    resolved_ref: Optional[str] = Field(default=None, description="Resolved branch or tag name")
    snapshot_path: Optional[str] = Field(default=None, description="Filesystem path to immutable snapshot directory")
    tree_hash: Optional[str] = Field(default=None, description="SHA-256 tree hash of snapshot manifest")
    total_bytes: int = Field(default=0, description="Uncompressed snapshot byte size")
    total_files: int = Field(default=0, description="Snapshot file count")
    technologies: Optional[TechnologyDetectionResult] = Field(
        default=None, description="Static technology and framework detection result"
    )
    is_duplicate_snapshot: bool = Field(
        default=False, description="True if an existing identical commit snapshot was reused"
    )
    error_reason: Optional[IngestionFailureReason] = Field(
        default=None, description="Structured failure category if ingestion was unsuccessful"
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error diagnostic message"
    )
    duration_ms: int = Field(default=0, description="Ingestion processing latency in milliseconds")
