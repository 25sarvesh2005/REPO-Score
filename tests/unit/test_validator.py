"""
Unit tests for repository reference and git ref validation engine.
"""

import pytest

from backend.repository.validator import (
    InvalidReferenceError,
    InvalidRepositoryUrlError,
    is_full_commit_sha,
    validate_and_parse_repository_url,
    validate_git_ref,
)


def test_valid_github_https_url() -> None:
    ref = validate_and_parse_repository_url("https://github.com/fastapi/fastapi")
    assert ref.owner == "fastapi"
    assert ref.name == "fastapi"
    assert ref.canonical_url == "https://github.com/fastapi/fastapi"
    assert ref.is_shorthand is False


def test_valid_github_url_with_git_suffix_and_slash() -> None:
    ref = validate_and_parse_repository_url("https://github.com/psf/requests.git/")
    assert ref.owner == "psf"
    assert ref.name == "requests"
    assert ref.canonical_url == "https://github.com/psf/requests"


def test_valid_shorthand_notation() -> None:
    ref = validate_and_parse_repository_url("tiangolo/fastapi")
    assert ref.owner == "tiangolo"
    assert ref.name == "fastapi"
    assert ref.canonical_url == "https://github.com/tiangolo/fastapi"
    assert ref.is_shorthand is True


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://github.com/org/repo",  # HTTP rejected
        "https://gitlab.com/org/repo",  # Non-github host
        "https://127.0.0.1/org/repo",  # IP address / SSRF
        "https://169.254.169.254/latest/meta-data",  # Cloud metadata SSRF
        "file:///etc/passwd",  # Local file protocol
        "ftp://github.com/org/repo",  # FTP protocol
        "git@github.com:org/repo.git",  # SSH format
        "https://github.com/../evil/repo",  # Path traversal attempt
        "",  # Empty
        "not-a-valid-url",  # Malformed
    ],
)
def test_reject_invalid_or_malicious_urls(invalid_url: str) -> None:
    with pytest.raises(InvalidRepositoryUrlError):
        validate_and_parse_repository_url(invalid_url)


def test_valid_git_references() -> None:
    assert validate_git_ref("main") == "main"
    assert validate_git_ref("feature/login-v2") == "feature/login-v2"
    assert validate_git_ref("v1.2.3") == "v1.2.3"
    assert validate_git_ref("release-2026.10") == "release-2026.10"
    full_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4"
    assert validate_git_ref(full_sha) == full_sha
    assert is_full_commit_sha(full_sha) is True
    assert is_full_commit_sha("main") is False


@pytest.mark.parametrize(
    "malicious_ref",
    [
        "main; rm -rf /",
        "main && whoami",
        "main | cat /etc/passwd",
        "$(whoami)",
        "`id`",
        "main\nnewline_command",
        "-malicious-flag",
        "/absolute/path",
        "feature/../traversal",
        "bad.lock",
        "a" * 129,  # Exceeds max length
    ],
)
def test_reject_malicious_or_invalid_git_refs(malicious_ref: str) -> None:
    with pytest.raises(InvalidReferenceError):
        validate_git_ref(malicious_ref)
