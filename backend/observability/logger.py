"""
Structured JSON logger with automated secret redaction and correlation context tracking.
"""

from contextvars import ContextVar
import json
import logging
import re
import sys
from typing import Any, Dict, Optional

# Context variables for request and evaluation tracing
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
evaluation_id_ctx: ContextVar[Optional[str]] = ContextVar("evaluation_id", default=None)

# Secret detection regexes
SECRET_PATTERNS = [
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}"), "[REDACTED_GH_PAT]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)(aws_secret_access_key|secret_key|aws_key|api_key)\s*[:=]\s*['\"][a-zA-Z0-9/+=]{30,}['\"]"), r'\1 = "[REDACTED_SECRET]"'),
    (re.compile(r"bearer\s+[a-zA-Z0-9_.\-~+/]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN[ A-Z0-9_-]+PRIVATE KEY-----.*?-----END[ A-Z0-9_-]+PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"postgres(ql)?://([^:]+):([^@]+)@", re.IGNORECASE), r"postgresql://\2:[REDACTED]@"),
]


def redact_secrets(text: str) -> str:
    """Mask known secret patterns with safe placeholders."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON lines with correlation context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
            "module": record.module,
            "line": record.lineno,
        }

        # Inject correlation identifiers if present in context
        corr_id = correlation_id_ctx.get()
        if corr_id:
            log_entry["correlation_id"] = corr_id

        eval_id = evaluation_id_ctx.get()
        if eval_id:
            log_entry["evaluation_id"] = eval_id

        # Attach exception trace if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Attach extra fields if passed
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            for k, v in record.extra_data.items():
                if isinstance(v, str):
                    log_entry[k] = redact_secrets(v)
                else:
                    log_entry[k] = v

        return json.dumps(log_entry)


def get_logger(name: str = "reposcore") -> logging.Logger:
    """Retrieve a configured structured logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
