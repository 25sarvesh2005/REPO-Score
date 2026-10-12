"""
Unit tests for sandbox environment isolation, output buffer truncation, and secret redaction.
"""

from backend.sandbox.sanitizer import (
    redact_sandbox_output,
    sanitize_environment,
    truncate_output,
)


def test_sanitize_environment_strips_host_secrets() -> None:
    host_env = {
        "DATABASE_URL": "postgresql://admin:secret@localhost:5432/db",
        "REDIS_PASSWORD": "supersecretpassword",
        "GITHUB_TOKEN": "ghp_1234567890abcdef1234567890abcdef1234",
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "MY_CUSTOM_SECRET": "topsecret",
        "PYTHONPATH": "/custom/path",
        "NODE_ENV": "production",
    }

    clean_env = sanitize_environment(host_env)

    # Must contain default safe variables
    assert clean_env["USER"] == "sandbox"
    assert clean_env["HOME"] == "/home/sandbox"

    # Must preserve allowed variables
    assert clean_env["PYTHONPATH"] == "/custom/path"
    assert clean_env["NODE_ENV"] == "production"

    # Must NOT contain host secrets
    assert "DATABASE_URL" not in clean_env
    assert "REDIS_PASSWORD" not in clean_env
    assert "GITHUB_TOKEN" not in clean_env
    assert "AWS_SECRET_ACCESS_KEY" not in clean_env
    assert "MY_CUSTOM_SECRET" not in clean_env


def test_truncate_output_within_limit() -> None:
    text = "Hello Sandbox Output"
    result, is_truncated = truncate_output(text, max_bytes=100)
    assert result == text
    assert is_truncated is False


def test_truncate_output_exceeding_limit() -> None:
    text = "A" * 200
    result, is_truncated = truncate_output(text, max_bytes=50)
    assert is_truncated is True
    assert "[TRUNCATED: Maximum step output buffer exceeded]" in result
    # Encoded prefix before truncation message is 50 bytes
    assert result.startswith("A" * 50)


def test_redact_sandbox_output() -> None:
    raw_output = (
        "Build log with ghp_111122223333444455556666777788889999 and "
        "AKIAIOSFODNN7EXAMPLE key, plus postgresql://dbuser:pass123@localhost:5432/mydb"
    )

    clean_output = redact_sandbox_output(raw_output)

    assert "ghp_" not in clean_output
    assert "[REDACTED_GH_TOKEN]" in clean_output
    assert "AKIAIOSFODNN7EXAMPLE" not in clean_output
    assert "[REDACTED_AWS_KEY]" in clean_output
    assert "pass123" not in clean_output
    assert "[REDACTED]@" in clean_output
