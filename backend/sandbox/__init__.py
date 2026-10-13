"""
Sandbox execution subsystem and isolation perimeter.
"""

from backend.sandbox.docker import DockerSandbox, DockerSandboxManager
from backend.sandbox.exceptions import (
    SandboxError,
    SandboxOOMError,
    SandboxSecurityViolationError,
    SandboxTimeoutError,
    SandboxUnavailableError,
)
from backend.sandbox.interface import ISandbox, ISandboxManager
from backend.sandbox.models import (
    NetworkPolicy,
    SandboxConfig,
    SandboxExecutionResult,
    SandboxState,
)
from backend.sandbox.sanitizer import (
    redact_sandbox_output,
    sanitize_environment,
    truncate_output,
)
from backend.sandbox.service import SandboxService
from backend.sandbox.validator import (
    parse_memory_mb,
    validate_sandbox_security_invariants,
)

__all__ = [
    "DockerSandbox",
    "DockerSandboxManager",
    "ISandbox",
    "ISandboxManager",
    "NetworkPolicy",
    "SandboxConfig",
    "SandboxError",
    "SandboxExecutionResult",
    "SandboxOOMError",
    "SandboxSecurityViolationError",
    "SandboxService",
    "SandboxState",
    "SandboxTimeoutError",
    "SandboxUnavailableError",
    "parse_memory_mb",
    "redact_sandbox_output",
    "sanitize_environment",
    "truncate_output",
    "validate_sandbox_security_invariants",
]
