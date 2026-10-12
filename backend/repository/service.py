"""
Repository Ingestion Orchestrator.
Coordinates URL validation, hardened cloning, snapshot manifest generation, deduplication, and technology detection.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
import tempfile
import time
from typing import Optional
import uuid

from backend.core.config import settings
from backend.repository.detector import detect_technologies_and_category
from backend.repository.ingestion import (
    GitIngestionClient,
    IngestionError,
)
from backend.repository.models import (
    IngestionFailureReason,
    IngestionResult,
    TechnologyDetectionResult,
)
from backend.repository.snapshot import (
    RepositoryFileCountExceededError,
    RepositorySizeExceededError,
    SnapshotSecurityError,
    build_snapshot_manifest,
    make_directory_read_only,
    safe_remove_directory,
)
from backend.repository.validator import validate_and_parse_repository_url

logger = logging.getLogger(__name__)


class RepositoryIngestionService:
    """
    Coordinates safe, isolated repository ingestion and immutable snapshot archiving.
    """

    def __init__(
        self,
        storage_root: Optional[Path] = None,
        git_client: Optional[GitIngestionClient] = None,
    ) -> None:
        self.storage_root = (storage_root or Path(settings.SNAPSHOT_STORAGE_PATH)).resolve()
        self.git_client = git_client or GitIngestionClient()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    async def ingest_repository(
        self,
        raw_url: str,
        ref: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest a remote Git repository safely into an immutable local snapshot.
        
        Execution steps:
        1. Validate and normalize repository reference (SSRF protection).
        2. Perform shallow clone with hooks neutralized.
        3. Resolve full 40-character commit SHA.
        4. Check for snapshot deduplication.
        5. Verify size quotas and compute cryptographic SHA-256 tree hash.
        6. Statically analyze technologies and operational evaluator category.
        7. Set directory permissions to read-only.
        """
        start_time = time.monotonic()
        temp_dir: Optional[Path] = None

        try:
            # Step 1: Validate repository URL and ref
            repo_ref = validate_and_parse_repository_url(raw_url, ref)
            canonical_url = repo_ref.canonical_url
            target_ref = repo_ref.ref

            # Step 2: Clone into isolated temporary directory first
            temp_staging_base = self.storage_root / ".tmp"
            temp_staging_base.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(tempfile.mkdtemp(prefix="ingest_", dir=str(temp_staging_base)))

            logger.info(
                "Initiating safe shallow clone",
                extra={
                    "repository_url": canonical_url,
                    "target_ref": target_ref,
                },
            )

            clone_meta = await self.git_client.clone_repository(
                canonical_url=canonical_url,
                target_dir=temp_dir,
                ref=target_ref,
            )

            resolved_commit_sha = clone_meta["commit_sha"]

            # Step 3: Destination storage path: {storage_root}/{owner}_{name}/{commit_sha}
            repo_slug = f"{repo_ref.owner}_{repo_ref.name}"
            destination_dir = self.storage_root / repo_slug / resolved_commit_sha

            # Step 4: Check snapshot deduplication
            if destination_dir.exists():
                logger.info(
                    "Snapshot already exists for commit SHA; deduplicating",
                    extra={"commit_sha": resolved_commit_sha, "destination": str(destination_dir)},
                )
                safe_remove_directory(temp_dir)
                temp_dir = None

                # Compute manifest and detection on existing snapshot
                manifest = build_snapshot_manifest(destination_dir, resolved_commit_sha)
                tech_result = detect_technologies_and_category(destination_dir)
                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                return IngestionResult(
                    success=True,
                    repository_url=canonical_url,
                    resolved_commit_sha=resolved_commit_sha,
                    resolved_ref=target_ref,
                    snapshot_path=str(destination_dir),
                    tree_hash=manifest.tree_hash,
                    total_bytes=manifest.total_bytes,
                    total_files=manifest.total_files,
                    technologies=tech_result,
                    is_duplicate_snapshot=True,
                    duration_ms=elapsed_ms,
                )

            # Step 5: Remove .git directory from snapshot before archiving to ensure immutability
            dot_git_dir = temp_dir / ".git"
            if dot_git_dir.exists():
                safe_remove_directory(dot_git_dir)

            # Move from temp staging to final destination
            destination_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_dir), str(destination_dir))
            temp_dir = None

            # Step 6: Build tamper-evident manifest and compute tree hash
            manifest = build_snapshot_manifest(destination_dir, resolved_commit_sha)

            # Step 7: Static technology detection
            tech_result = detect_technologies_and_category(destination_dir)

            # Step 8: Seal snapshot as read-only
            make_directory_read_only(destination_dir)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            logger.info(
                "Repository ingestion completed successfully",
                extra={
                    "commit_sha": resolved_commit_sha,
                    "tree_hash": manifest.tree_hash,
                    "total_bytes": manifest.total_bytes,
                    "total_files": manifest.total_files,
                    "primary_language": tech_result.primary_language,
                    "category": tech_result.evaluator_category.value,
                },
            )

            return IngestionResult(
                success=True,
                repository_url=canonical_url,
                resolved_commit_sha=resolved_commit_sha,
                resolved_ref=target_ref,
                snapshot_path=str(destination_dir),
                tree_hash=manifest.tree_hash,
                total_bytes=manifest.total_bytes,
                total_files=manifest.total_files,
                technologies=tech_result,
                is_duplicate_snapshot=False,
                duration_ms=elapsed_ms,
            )

        except IngestionError as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Ingestion error: %s", exc.detail, extra={"code": exc.code})
            return IngestionResult(
                success=False,
                repository_url=raw_url,
                error_reason=exc.reason,
                error_message=exc.detail,
                duration_ms=elapsed_ms,
            )

        except (RepositorySizeExceededError, RepositoryFileCountExceededError, SnapshotSecurityError) as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            reason = (
                IngestionFailureReason.SIZE_EXCEEDED
                if isinstance(exc, RepositorySizeExceededError)
                else IngestionFailureReason.FILE_COUNT_EXCEEDED
                if isinstance(exc, RepositoryFileCountExceededError)
                else IngestionFailureReason.PATH_TRAVERSAL_DETECTED
            )
            logger.error("Snapshot constraint violation: %s", exc.detail)
            return IngestionResult(
                success=False,
                repository_url=raw_url,
                error_reason=reason,
                error_message=exc.detail,
                duration_ms=elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception("Unexpected error during repository ingestion: %s", exc)
            return IngestionResult(
                success=False,
                repository_url=raw_url,
                error_reason=IngestionFailureReason.UNKNOWN_FAILURE,
                error_message=str(exc),
                duration_ms=elapsed_ms,
            )

        finally:
            if temp_dir and temp_dir.exists():
                safe_remove_directory(temp_dir)
