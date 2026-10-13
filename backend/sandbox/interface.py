"""
Abstract interface contracts for container sandbox lifecycle and execution management.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.sandbox.models import SandboxConfig, SandboxExecutionResult, SandboxState


class ISandbox(ABC):
    """Abstract handle for an active ephemeral sandbox container instance."""

    @property
    @abstractmethod
    def container_id(self) -> str:
        """Unique identifier of the running sandbox container."""
        pass

    @property
    @abstractmethod
    def state(self) -> SandboxState:
        """Current lifecycle status of the container."""
        pass

    @abstractmethod
    async def execute(
        self,
        command: list[str],
        timeout_seconds: int | None = None,
    ) -> SandboxExecutionResult:
        """
        Execute a command inside the isolated container and stream/collect results.
        """
        pass

    @abstractmethod
    async def terminate(self) -> None:
        """Forcefully terminate and purge the container instance and its ephemeral mounts."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Query cgroups resource metrics (CPU usage, memory usage, PID count)."""
        pass

    async def __aenter__(self) -> "ISandbox":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.terminate()


class ISandboxManager(ABC):
    """Abstract orchestrator for spawning, tracking, and sweeping sandboxes."""

    @abstractmethod
    async def create_sandbox(self, config: SandboxConfig) -> ISandbox:
        """Spawn a new ephemeral sandbox adhering strictly to the provided security config."""
        pass

    @abstractmethod
    async def cleanup_orphans(self, older_than_seconds: int = 600) -> int:
        """Purge lingering or dangling containers exceeding global execution thresholds."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the backing execution runtime is reachable and operational."""
        pass
