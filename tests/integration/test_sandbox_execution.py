"""
Integration tests for sandbox execution lifecycle, timeouts, OOM kills, and runtime availability.
"""

from pathlib import Path
import pytest

from backend.sandbox.docker import DockerSandboxManager
from backend.sandbox.exceptions import (
    SandboxError,
    SandboxSecurityViolationError,
    SandboxUnavailableError,
)
from backend.sandbox.mock import MockSandboxManager
from backend.sandbox.models import NetworkPolicy, SandboxConfig, SandboxState
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
async def test_mock_sandbox_execution_success(base_config: SandboxConfig) -> None:
    manager = MockSandboxManager()
    sandbox = await manager.create_sandbox(base_config)

    assert sandbox.state == SandboxState.RUNNING

    result = await sandbox.execute(["pytest", "-v"])
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.oom_killed is False
    assert "Mock execution succeeded" in result.stdout

    # Verify resource stats query
    stats = await sandbox.get_stats()
    assert "memory_usage" in stats
    assert stats["memory_limit"] == 2147483648

    await sandbox.terminate()
    assert sandbox.state == SandboxState.TERMINATED


@pytest.mark.asyncio
async def test_mock_sandbox_timeout_simulation(base_config: SandboxConfig) -> None:
    manager = MockSandboxManager()
    sandbox = await manager.create_sandbox(base_config)

    result = await sandbox.execute(["python", "script.py", "trigger:timeout"])
    assert result.timed_out is True
    assert result.exit_code == 124
    assert "timeout" in result.stderr.lower()

    await sandbox.terminate()


@pytest.mark.asyncio
async def test_mock_sandbox_oom_simulation(base_config: SandboxConfig) -> None:
    manager = MockSandboxManager()
    sandbox = await manager.create_sandbox(base_config)

    result = await sandbox.execute(["python", "run_hog.py", "trigger:oom"])
    assert result.oom_killed is True
    assert result.exit_code == 137
    assert "out-of-memory" in result.stderr.lower()

    await sandbox.terminate()


@pytest.mark.asyncio
async def test_mock_sandbox_orphan_cleanup(base_config: SandboxConfig) -> None:
    manager = MockSandboxManager()
    sbx1 = await manager.create_sandbox(base_config)
    sbx2 = await manager.create_sandbox(base_config)

    assert sbx1.state == SandboxState.RUNNING
    assert sbx2.state == SandboxState.RUNNING

    purged = await manager.cleanup_orphans(older_than_seconds=0)
    assert purged == 2
    assert sbx1.state == SandboxState.TERMINATED
    assert sbx2.state == SandboxState.TERMINATED


@pytest.mark.asyncio
async def test_docker_manager_unavailable_raises_without_host_fallback(base_config: SandboxConfig) -> None:
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
