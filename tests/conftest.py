"""
Standard pytest fixtures for RepoScore test suite.
"""

from unittest.mock import AsyncMock

import pytest

from backend.sandbox.models import SandboxExecutionResult, SandboxState


@pytest.fixture
def make_mock_sandbox():
    """Factory fixture returning an AsyncMock sandbox with realistic default telemetry."""

    def _create(execute_handler=None):
        sbx = AsyncMock()
        sbx.state = SandboxState.RUNNING
        sbx.get_stats = AsyncMock(
            return_value={
                "memory_usage": 52428800,
                "memory_limit": 2147483648,
                "cpu_usage": 0.05,
            }
        )
        sbx.terminate = AsyncMock()
        if execute_handler:
            sbx.execute = AsyncMock(side_effect=execute_handler)
        else:
            sbx.execute = AsyncMock(
                return_value=SandboxExecutionResult(
                    exit_code=0,
                    stdout="Execution succeeded",
                    stderr="",
                )
            )
        return sbx

    return _create
