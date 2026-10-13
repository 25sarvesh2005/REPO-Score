"""
Sandbox orchestration service and standard configuration builders.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from backend.core.config import settings
from backend.sandbox.docker import DockerSandboxManager
from backend.sandbox.interface import ISandbox, ISandboxManager
from backend.sandbox.models import NetworkPolicy, SandboxConfig


class SandboxService:
    """
    Central orchestration facade for managing ephemeral evaluation sandboxes.
    """

    def __init__(self, manager: ISandboxManager | None = None) -> None:
        self._manager = manager or DockerSandboxManager()

    @property
    def manager(self) -> ISandboxManager:
        return self._manager

    def set_manager(self, manager: ISandboxManager) -> None:
        """Allow switching manager implementation."""
        self._manager = manager

    @asynccontextmanager
    async def ephemeral_sandbox(
        self,
        config: SandboxConfig,
    ) -> AsyncGenerator[ISandbox, None]:
        """
        Asynchronous context manager ensuring clean initialization, execution,
        and guaranteed termination/teardown of the ephemeral container sandbox.
        """
        sandbox = await self._manager.create_sandbox(config)
        try:
            yield sandbox
        finally:
            await sandbox.terminate()

    @staticmethod
    def build_python_sandbox_config(
        snapshot_dir: Path,
        evaluation_id: str,
        network_mode: NetworkPolicy = NetworkPolicy.NONE,
        timeout_seconds: int = 60,
    ) -> SandboxConfig:
        """
        Build a hardened SandboxConfig tailored for Python repository evaluation.
        """
        return SandboxConfig(
            image=settings.SANDBOX_DEFAULT_IMAGE_PYTHON,
            workdir="/workspace/build",
            user="10001:10001",
            read_only_rootfs=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            network_mode=network_mode,
            memory_limit=f"{settings.SANDBOX_MAX_MEMORY_MB}m",
            memory_swap=f"{settings.SANDBOX_MAX_MEMORY_MB}m",
            cpu_quota=settings.SANDBOX_MAX_CPUS,
            pids_limit=settings.SANDBOX_MAX_PIDS,
            tmpfs_mounts={
                "/workspace/build": "rw,nosuid,nodev,size=1024m",
                "/tmp": "rw,nosuid,nodev,size=256m",
            },
            bind_mounts={
                str(snapshot_dir.resolve()): {
                    "bind": "/workspace/src",
                    "mode": "ro",
                }
            },
            environment={
                "PYTHONPATH": "/workspace/src:/workspace/build",
                "PYTHONUNBUFFERED": "1",
            },
            timeout_seconds=timeout_seconds,
            labels={
                "reposcore.evaluation_id": evaluation_id,
            },
        )

    @staticmethod
    def build_node_sandbox_config(
        snapshot_dir: Path,
        evaluation_id: str,
        network_mode: NetworkPolicy = NetworkPolicy.NONE,
        timeout_seconds: int = 60,
    ) -> SandboxConfig:
        """
        Build a hardened SandboxConfig tailored for Node.js repository evaluation.
        """
        return SandboxConfig(
            image=settings.SANDBOX_DEFAULT_IMAGE_NODE,
            workdir="/workspace/build",
            user="10001:10001",
            read_only_rootfs=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            network_mode=network_mode,
            memory_limit=f"{settings.SANDBOX_MAX_MEMORY_MB}m",
            memory_swap=f"{settings.SANDBOX_MAX_MEMORY_MB}m",
            cpu_quota=settings.SANDBOX_MAX_CPUS,
            pids_limit=settings.SANDBOX_MAX_PIDS,
            tmpfs_mounts={
                "/workspace/build": "rw,nosuid,nodev,size=1024m",
                "/tmp": "rw,nosuid,nodev,size=256m",
            },
            bind_mounts={
                str(snapshot_dir.resolve()): {
                    "bind": "/workspace/src",
                    "mode": "ro",
                }
            },
            environment={
                "NODE_PATH": "/workspace/build/node_modules",
                "NODE_ENV": "production",
            },
            timeout_seconds=timeout_seconds,
            labels={
                "reposcore.evaluation_id": evaluation_id,
            },
        )
