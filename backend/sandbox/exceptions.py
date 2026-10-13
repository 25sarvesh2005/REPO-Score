"""
Domain exceptions for sandbox security violations, lifecycle errors, and resource exhaustions.
"""

from backend.api.errors import RepoScoreException


class SandboxError(RepoScoreException):
    """Base exception for all container sandbox failures."""

    def __init__(
        self,
        detail: str,
        title: str = "Sandbox Execution Error",
        status_code: int = 500,
        code: str = "SANDBOX_ERROR",
    ) -> None:
        super().__init__(
            detail=detail,
            title=title,
            status_code=status_code,
            error_type=f"https://reposcore.internal/errors/sandbox/{code.lower()}",
        )
        self.code = code


class SandboxSecurityViolationError(SandboxError):
    """Raised when a sandbox configuration violates critical security isolation invariants."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            title="Sandbox Security Invariant Violation",
            status_code=400,
            code="SANDBOX_SECURITY_VIOLATION",
        )


class SandboxTimeoutError(SandboxError):
    """Raised when sandbox command execution exceeds allocated timeout ceiling."""

    def __init__(self, detail: str = "Sandbox command execution timed out.") -> None:
        super().__init__(
            detail=detail,
            title="Sandbox Execution Timeout",
            status_code=504,
            code="SANDBOX_TIMEOUT",
        )


class SandboxOOMError(SandboxError):
    """Raised when container process is terminated by the kernel Out-Of-Memory killer."""

    def __init__(
        self, detail: str = "Sandbox process terminated due to memory quota exhaustion (OOM)."
    ) -> None:
        super().__init__(
            detail=detail,
            title="Sandbox Out-Of-Memory",
            status_code=422,
            code="SANDBOX_OOM_KILLED",
        )


class SandboxUnavailableError(SandboxError):
    """
    Raised when container execution engine is unavailable.
    CRITICAL: Untrusted repository code MUST NEVER fall back to host execution!
    """

    def __init__(
        self,
        detail: str = "Container execution runtime is unavailable. Host execution fallback is strictly prohibited.",
    ) -> None:
        super().__init__(
            detail=detail,
            title="Sandbox Runtime Unavailable",
            status_code=503,
            code="SANDBOX_UNAVAILABLE",
        )
