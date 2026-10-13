"""
Unit tests for SandboxService configuration factories and lifecycle context manager.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.sandbox.interface import ISandboxManager
from backend.sandbox.models import NetworkPolicy, SandboxExecutionResult, SandboxState
from backend.sandbox.service import SandboxService


def test_build_python_sandbox_config(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "test_snapshot"
    snapshot_dir.mkdir()
    eval_id = "eval-12345"

    config = SandboxService.build_python_sandbox_config(
        snapshot_dir=snapshot_dir,
        evaluation_id=eval_id,
        network_mode=NetworkPolicy.NONE,
    )

    assert config.user == "10001:10001"
    assert config.read_only_rootfs is True
    assert config.cap_drop == ["ALL"]
    assert "no-new-privileges:true" in config.security_opt
    assert config.network_mode == NetworkPolicy.NONE
    assert "/workspace/build" in config.tmpfs_mounts
    assert "/tmp" in config.tmpfs_mounts

    # Bind mount of snapshot must be read-only
    abs_snapshot = str(snapshot_dir.resolve())
    assert abs_snapshot in config.bind_mounts
    assert config.bind_mounts[abs_snapshot]["mode"] == "ro"
    assert config.bind_mounts[abs_snapshot]["bind"] == "/workspace/src"
    assert config.labels["reposcore.evaluation_id"] == eval_id


def test_build_node_sandbox_config(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "test_snapshot_node"
    snapshot_dir.mkdir()
    eval_id = "eval-67890"

    config = SandboxService.build_node_sandbox_config(
        snapshot_dir=snapshot_dir,
        evaluation_id=eval_id,
        network_mode=NetworkPolicy.BUILD_PROXY,
    )

    assert config.network_mode == NetworkPolicy.BUILD_PROXY
    assert config.read_only_rootfs is True
    assert config.labels["reposcore.evaluation_id"] == eval_id


@pytest.mark.asyncio
async def test_ephemeral_sandbox_lifecycle(tmp_path: Path) -> None:
    mock_sbx = AsyncMock()
    mock_sbx.state = SandboxState.RUNNING
    mock_sbx.container_id = "test-sbx-123"
    mock_sbx.execute = AsyncMock(
        return_value=SandboxExecutionResult(
            exit_code=0, stdout="Command executed: print('hello')", stderr=""
        )
    )

    async def _terminate():
        mock_sbx.state = SandboxState.TERMINATED

    mock_sbx.terminate = AsyncMock(side_effect=_terminate)

    mock_manager = AsyncMock(spec=ISandboxManager)
    mock_manager.create_sandbox = AsyncMock(return_value=mock_sbx)
    service = SandboxService(manager=mock_manager)

    snapshot_dir = tmp_path / "lifecycle_snap"
    snapshot_dir.mkdir()

    config = SandboxService.build_python_sandbox_config(
        snapshot_dir=snapshot_dir,
        evaluation_id="eval-lifecycle",
    )

    captured_sandbox = None
    async with service.ephemeral_sandbox(config) as sbx:
        captured_sandbox = sbx
        assert sbx.state == SandboxState.RUNNING
        assert sbx.container_id.startswith("test-sbx-")

        # Execute command inside sandbox
        res = await sbx.execute(["python", "-c", "print('hello')"])
        assert res.exit_code == 0
        assert "Command executed" in res.stdout

    # Once exited from context manager, sandbox must be terminated
    assert captured_sandbox is not None
    assert captured_sandbox.state == SandboxState.TERMINATED
