"""
Hardened asynchronous Git ingestion engine with hook neutralization and resource bounding.
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Dict, Optional, Tuple

from backend.api.errors import RepoScoreException
from backend.core.config import settings
from backend.repository.models import IngestionFailureReason
from backend.repository.snapshot import safe_remove_directory
from backend.repository.validator import is_full_commit_sha

logger = logging.getLogger(__name__)


class IngestionError(RepoScoreException):
    """Base exception for Git repository ingestion failures."""

    def __init__(self, detail: str, reason: IngestionFailureReason, status_code: int = 400) -> None:
        super().__init__(
            detail=detail,
            title="Repository Ingestion Failure",
            status_code=status_code,
            error_type=f"https://reposcore.internal/errors/ingestion/{reason.value.lower()}",
        )
        self.reason = reason
        self.code = reason.value


class IngestionTimeoutError(IngestionError):
    """Raised when git clone or fetch exceeds execution timeout."""

    def __init__(self, detail: str = "Repository clone timed out.") -> None:
        super().__init__(
            detail=detail,
            reason=IngestionFailureReason.TIMEOUT,
            status_code=504,
        )


class IngestionNotFoundError(IngestionError):
    """Raised when repository does not exist on upstream host."""

    def __init__(self, detail: str = "Repository not found or inaccessible.") -> None:
        super().__init__(
            detail=detail,
            reason=IngestionFailureReason.REPOSITORY_NOT_FOUND,
            status_code=404,
        )


class IngestionAuthError(IngestionError):
    """Raised when authentication is required for private or restricted repository."""

    def __init__(self, detail: str = "Authentication required to access repository.") -> None:
        super().__init__(
            detail=detail,
            reason=IngestionFailureReason.AUTH_REQUIRED,
            status_code=403,
        )


class IngestionCorruptGitError(IngestionError):
    """Raised when git objects or repository tree are corrupted."""

    def __init__(self, detail: str = "Repository contains corrupted Git objects.") -> None:
        super().__init__(
            detail=detail,
            reason=IngestionFailureReason.CORRUPT_GIT_OBJECTS,
            status_code=422,
        )


class GitIngestionClient:
    """
    Hardened Git ingestion engine.
    
    Guarantees:
    - Never executes repository hooks (`core.hooksPath=/dev/null`).
    - Disallows local filesystem protocols (`protocol.file.allow=never`).
    - Enforces depth-1 shallow clone to minimize egress.
    - Bound by strict timeout and graceful cancellation cleanup.
    """

    def __init__(
        self,
        timeout_seconds: Optional[int] = None,
        allow_submodules: bool = False,
    ) -> None:
        self.timeout_seconds = timeout_seconds or settings.INGESTION_TIMEOUT_SECONDS
        self.allow_submodules = allow_submodules

    async def _run_git_command(
        self,
        args: list[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[int, str, str]:
        """Execute a git command with timeout and process cleanup."""
        cmd_timeout = timeout or self.timeout_seconds
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Enforce clean environment without inherited dangerous git configurations
                env={
                    **os.environ,
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_OPTIONAL_LOCKS": "0",
                },
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=cmd_timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            return process.returncode or 0, stdout, stderr

        except asyncio.TimeoutError as exc:
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise IngestionTimeoutError(
                f"Git operation timed out after {cmd_timeout} seconds."
            ) from exc

        except asyncio.CancelledError:
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise

    def _classify_git_error(self, stderr: str, returncode: int) -> IngestionError:
        """Categorize git command failure output into structured domain errors."""
        lower_err = stderr.lower()
        if "not found" in lower_err or "could not read from remote" in lower_err or "404" in lower_err:
            return IngestionNotFoundError(f"Repository not found or inaccessible: {stderr}")
        if "authentication" in lower_err or "permission denied" in lower_err or "invalid username or password" in lower_err:
            return IngestionAuthError(f"Authentication failed or repository is private: {stderr}")
        if "rate limit" in lower_err or "429" in lower_err:
            return IngestionError(f"GitHub API rate limit exceeded: {stderr}", IngestionFailureReason.RATE_LIMITED, 429)
        if "corrupt" in lower_err or "fatal: bad object" in lower_err or "pack has" in lower_err:
            return IngestionCorruptGitError(f"Corrupt Git objects encountered: {stderr}")
        return IngestionError(
            f"Git operation failed with exit code {returncode}: {stderr}",
            IngestionFailureReason.UNKNOWN_FAILURE,
            400,
        )

    async def clone_repository(
        self,
        canonical_url: str,
        target_dir: Path,
        ref: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Safely clone a repository into target_dir.
        
        Returns metadata:
        - commit_sha: Resolved 40-character commit SHA
        - commit_message: Commit summary
        - author_name: Author name
        - commit_date: ISO 8601 commit timestamp
        """
        # Hardened git arguments
        clone_args = [
            "-c", "core.hooksPath=/dev/null",
            "-c", "http.sslVerify=true",
            "-c", "protocol.file.allow=never",
            "clone",
            "--depth", "1",
        ]

        if not self.allow_submodules:
            clone_args.extend(["--recurse-submodules=no"])

        if ref and not is_full_commit_sha(ref):
            # Branch or tag name
            clone_args.extend(["--branch", ref])

        clone_args.extend([canonical_url, str(target_dir)])

        returncode, stdout, stderr = await self._run_git_command(clone_args)

        # If branch clone failed because requested branch was not found, fallback to upstream default branch
        if returncode != 0 and ref and not is_full_commit_sha(ref):
            if "remote branch" in stderr.lower() and "not found" in stderr.lower():
                logger.info(f"Requested branch '{ref}' not found upstream, falling back to default branch.")
                safe_remove_directory(target_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                fallback_branch_args = [
                    "-c", "core.hooksPath=/dev/null",
                    "-c", "http.sslVerify=true",
                    "-c", "protocol.file.allow=never",
                    "clone",
                    "--depth", "1",
                ]
                if not self.allow_submodules:
                    fallback_branch_args.extend(["--recurse-submodules=no"])
                fallback_branch_args.extend([canonical_url, str(target_dir)])
                returncode, stdout, stderr = await self._run_git_command(fallback_branch_args)

        # If shallow clone with branch failed because ref might be a raw commit SHA,
        # fallback to cloning default branch and checking out the specific SHA
        if returncode != 0 and ref and is_full_commit_sha(ref):
            # Clean target_dir before retry
            safe_remove_directory(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            fallback_args = [
                "-c", "core.hooksPath=/dev/null",
                "-c", "http.sslVerify=true",
                "-c", "protocol.file.allow=never",
                "clone",
                "--no-checkout",
                canonical_url,
                str(target_dir),
            ]
            returncode, stdout, stderr = await self._run_git_command(fallback_args)
            if returncode == 0:
                # Checkout specific commit SHA
                co_rc, co_out, co_err = await self._run_git_command(
                    ["checkout", ref], cwd=target_dir
                )
                if co_rc != 0:
                    safe_remove_directory(target_dir)
                    raise self._classify_git_error(co_err, co_rc)

        if returncode != 0:
            safe_remove_directory(target_dir)
            raise self._classify_git_error(stderr, returncode)

        # Neutralize any hooks inside .git
        hooks_dir = target_dir / ".git" / "hooks"
        if hooks_dir.exists():
            safe_remove_directory(hooks_dir)

        # Resolve exact 40-character commit SHA
        rc, sha_out, sha_err = await self._run_git_command(
            ["rev-parse", "HEAD"], cwd=target_dir
        )
        if rc != 0 or len(sha_out) != 40:
            safe_remove_directory(target_dir)
            raise IngestionCorruptGitError(f"Failed to resolve HEAD commit SHA: {sha_err}")

        commit_sha = sha_out.strip()

        # Extract commit metadata
        rc_meta, meta_out, _ = await self._run_git_command(
            ["log", "-1", "--format=%s%x00%an%x00%aI"], cwd=target_dir
        )
        commit_message, author_name, commit_date = "", "", ""
        if rc_meta == 0 and meta_out:
            parts = meta_out.split("\x00")
            if len(parts) >= 3:
                commit_message = parts[0]
                author_name = parts[1]
                commit_date = parts[2]

        return {
            "commit_sha": commit_sha,
            "commit_message": commit_message,
            "author_name": author_name,
            "commit_date": commit_date or datetime.now(timezone.utc).isoformat(),
        }
