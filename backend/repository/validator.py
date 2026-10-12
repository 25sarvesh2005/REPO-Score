"""
Repository URL and reference validation engine with SSRF and command-injection protection.
"""

import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse

from backend.api.errors import ValidationException
from backend.repository.models import RepositoryReference


class InvalidRepositoryUrlError(ValidationException):
    """Raised when repository URL is malformed, non-GitHub, or targets internal resources."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail)
        self.code = "INVALID_REPOSITORY_URL"


class InvalidReferenceError(ValidationException):
    """Raised when git branch, tag, or commit reference contains malicious or invalid characters."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail)
        self.code = "INVALID_GIT_REFERENCE"


# Regex patterns
GITHUB_SSH_OR_SHORTHAND_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
SAFE_REF_PATTERN = re.compile(r"^[A-Za-z0-9_./@#-]{1,128}$")
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def validate_and_parse_repository_url(
    raw_url: str, ref: Optional[str] = None
) -> RepositoryReference:
    """
    Validate, sanitize, and normalize a repository URL or shorthand reference.
    
    Guarantees:
    - Enforces HTTPS GitHub URLs only (or 'owner/repo' shorthand).
    - Prevents SSRF attacks against localhost, metadata endpoints, and internal networks.
    - Sanitizes ref strings against shell injection vulnerabilities.
    """
    if not raw_url or not isinstance(raw_url, str):
        raise InvalidRepositoryUrlError("Repository URL must be a non-empty string.")

    cleaned_url = raw_url.strip()

    # Check for shorthand notation 'owner/repo'
    shorthand_match = GITHUB_SSH_OR_SHORTHAND_PATTERN.match(cleaned_url)
    if shorthand_match:
        owner, name = shorthand_match.group(1), shorthand_match.group(2)
        # Verify neither component is a disguised path traversal or URL scheme
        if owner in {".", ".."} or name in {".", ".."}:
            raise InvalidRepositoryUrlError("Repository owner and name must not contain path traversal elements.")
        if name.endswith(".git"):
            name = name[:-4]
        canonical_url = f"https://github.com/{owner}/{name}"
        parsed_ref = validate_git_ref(ref) if ref else None
        return RepositoryReference(
            owner=owner,
            name=name,
            canonical_url=canonical_url,
            ref=parsed_ref,
            is_shorthand=True,
        )

    # Parse URL components
    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise InvalidRepositoryUrlError(f"Malformed URL: {exc}") from exc

    if parsed.scheme.lower() != "https":
        raise InvalidRepositoryUrlError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only HTTPS GitHub repositories are permitted."
        )

    hostname = (parsed.hostname or "").lower()

    # SSRF Protection: Reject IP addresses directly
    try:
        ipaddress.ip_address(hostname)
        raise InvalidRepositoryUrlError(
            "Direct IP address access is forbidden. Repository references must target github.com."
        )
    except ValueError:
        pass  # Hostname is not a raw IP address

    # Strict domain check
    if hostname != "github.com":
        raise InvalidRepositoryUrlError(
            f"Domain '{hostname}' is not supported. Only 'github.com' is currently authorized."
        )

    # Validate path structure
    match = GITHUB_URL_PATTERN.match(cleaned_url)
    if not match:
        raise InvalidRepositoryUrlError(
            "URL does not match standard GitHub format 'https://github.com/owner/repository'."
        )

    owner, name = match.group(1), match.group(2)
    if owner in {".", ".."} or name in {".", ".."}:
        raise InvalidRepositoryUrlError("Repository owner and name must not contain path traversal elements.")

    canonical_url = f"https://github.com/{owner}/{name}"
    parsed_ref = validate_git_ref(ref) if ref else None

    return RepositoryReference(
        owner=owner,
        name=name,
        canonical_url=canonical_url,
        ref=parsed_ref,
        is_shorthand=False,
    )


def validate_git_ref(ref: Optional[str]) -> Optional[str]:
    """
    Validate git reference (branch, tag, or 40-character hexadecimal commit SHA).
    Rejects any characters that could trigger command injection or path traversal.
    """
    if not ref:
        return None

    cleaned_ref = ref.strip()
    if not cleaned_ref:
        return None

    # Length constraint
    if len(cleaned_ref) > 128:
        raise InvalidReferenceError("Git reference exceeds maximum allowed length of 128 characters.")

    # Dangerous characters / traversal checks
    if any(c in cleaned_ref for c in [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r", "\0"]):
        raise InvalidReferenceError("Git reference contains illegal shell metacharacters.")

    if cleaned_ref.startswith("-") or cleaned_ref.startswith("/"):
        raise InvalidReferenceError("Git reference cannot start with a hyphen or forward slash.")

    if ".." in cleaned_ref or cleaned_ref.endswith(".lock"):
        raise InvalidReferenceError("Git reference contains invalid sequence ('..' or '.lock').")

    if not SAFE_REF_PATTERN.match(cleaned_ref):
        raise InvalidReferenceError(
            f"Git reference '{cleaned_ref}' contains characters outside the permitted pattern [A-Za-z0-9_./@#-]."
        )

    return cleaned_ref


def is_full_commit_sha(ref: str) -> bool:
    """Check if the provided ref is a 40-character hexadecimal commit SHA."""
    return bool(COMMIT_SHA_PATTERN.match(ref))
