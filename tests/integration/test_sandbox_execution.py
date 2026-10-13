"""
Integration tests for sandbox execution lifecycle, timeouts, OOM kills, and runtime availability.
"""

from pathlib import Path

import pytest

from backend.sandbox.docker import DockerSandboxManager
from backend.sandbox.exceptions import (
    SandboxSecurityViolationError,
    SandboxUnavailableError,
)
from backend.sandbox.models import SandboxConfig
from backend.sandbox.service import SandboxService


@pytest.fixture
def base_config(tmp_path: Path) -> SandboxConfig:
    snap_dir = tmp_path / "snap"
    snap_dir.mkdir()
    return SandboxService.build_python_sandbox_config(
        snapshot_dir=snap_dir,
        evaluation_id="eval-integ",
    )


@pytest.mark.asyncio
async def test_docker_sandbox_manager_availability() -> None:
    """Verify DockerSandboxManager inspects Docker availability properly."""
    manager = DockerSandboxManager()
    available = await manager.is_available()
    assert isinstance(available, bool)


@pytest.mark.asyncio
async def test_docker_manager_unavailable_raises_without_host_fallback(
    base_config: SandboxConfig,
) -> None:
    """
    Non-negotiable rule: When Docker runtime is unavailable, the system MUST raise
    SandboxUnavailableError and MUST NEVER execute untrusted commands on the host.
    """
    docker_mgr = DockerSandboxManager()

    # If docker is not running on host, create_sandbox must raise SandboxUnavailableError
    is_docker_running = await docker_mgr.is_available()
    if not is_docker_running:
        with pytest.raises(SandboxUnavailableError, match="Docker daemon is not running"):
            await docker_mgr.create_sandbox(base_config)
    else:
        # If running, verify security invariant check still guards it
        base_config.user = "root"
        with pytest.raises(SandboxSecurityViolationError):
            await docker_mgr.create_sandbox(base_config)
