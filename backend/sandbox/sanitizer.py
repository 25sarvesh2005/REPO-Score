"""
Security sanitization engine: Environment isolation, buffer truncation, and secret redaction.
"""

import re
from typing import Dict, Optional, Tuple

from backend.observability.logger import redact_secrets

# Permitted container environment variables (whitelist)
ALLOWED_ENV_VARS = {
    "PATH",
    "LANG",
    "LC_ALL",
    "HOME",
    "USER",
    "PYTHONPATH",
    "PYTHONUNBUFFERED",
    "NODE_PATH",
    "NODE_ENV",
    "RUSTUP_HOME",
    "CARGO_HOME",
    "GOPATH",
    "GOROOT",
    "DEBIAN_FRONTEND",
}

# Forbidden keywords in variable keys
SENSITIVE_KEY_SUBSTRINGS = {
    "TOKEN",
    "KEY",
    "SECRET",
    "PASS",
    "AUTH",
    "DATABASE",
    "REDIS",
    "AWS",
    "GITHUB",
    "CREDENTIAL",
    "PRIVATE",
}

DEFAULT_SANDBOX_ENV: Dict[str, str] = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "HOME": "/home/sandbox",
    "USER": "sandbox",
    "PYTHONPATH": "/workspace/src:/workspace/build",
    "PYTHONUNBUFFERED": "1",
    "NODE_PATH": "/workspace/build/node_modules",
}


def sanitize_environment(custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Construct a clean, strictly whitelisted environment dictionary.
    Eliminates all host credentials and environment variables.
    """
    clean_env = dict(DEFAULT_SANDBOX_ENV)

    if not custom_env:
        return clean_env

    for k, v in custom_env.items():
        upper_k = k.upper()
        # Verify key does not contain sensitive substrings
        if any(substr in upper_k for substr in SENSITIVE_KEY_SUBSTRINGS):
            continue

        # Check whitelist
        if upper_k in ALLOWED_ENV_VARS:
            clean_env[k] = str(v)

    return clean_env


def truncate_output(text: str, max_bytes: int = 10 * 1024 * 1024) -> Tuple[str, bool]:
    """
    Enforce hard output buffer limit (default 10MB) to prevent memory denial-of-service.
    Returns (truncated_text, is_truncated).
    """
    if not text:
        return "", False

    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False

    truncated_encoded = encoded[:max_bytes]
    truncated_str = truncated_encoded.decode("utf-8", errors="ignore")
    truncated_str += "\n[TRUNCATED: Maximum step output buffer exceeded]\n"
    return truncated_str, True


def redact_sandbox_output(text: str) -> str:
    """
    Apply multi-pattern regular expression redaction to scrub any potential leaked secrets
    from container stdout/stderr.
    """
    if not text:
        return ""
    return redact_secrets(text)
