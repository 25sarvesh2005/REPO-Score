"""
Isolated Mock Sandbox Manager for deterministic unit testing and verification.
Enforces security invariants, simulates cgroups limits, timeouts, and redaction WITHOUT host execution.
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from backend.sandbox.exceptions import (
    SandboxError,
    SandboxOOMError,
    SandboxTimeoutError,
)
from backend.sandbox.interface import ISandbox, ISandboxManager
from backend.sandbox.models import (
    SandboxConfig,
    SandboxExecutionResult,
    SandboxState,
)
from backend.sandbox.sanitizer import (
    redact_sandbox_output,
    sanitize_environment,
    truncate_output,
)
from backend.sandbox.validator import validate_sandbox_security_invariants


class MockSandbox(ISandbox):
    """
    Simulated container sandbox that mimics isolated execution semantics.
    Guarantees zero execution of arbitrary untrusted repository code on the host.
    """

    def __init__(
        self,
        container_id: str,
        config: SandboxConfig,
        command_handler: Optional[Callable[[List[str]], SandboxExecutionResult]] = None,
    ) -> None:
        self._container_id = container_id
        self._config = config
        self._state = SandboxState.RUNNING
        self._command_handler = command_handler
        self._executed_commands: List[List[str]] = []

    @property
    def container_id(self) -> str:
        return self._container_id

    @property
    def state(self) -> SandboxState:
        return self._state

    @property
    def executed_commands(self) -> List[List[str]]:
        return self._executed_commands

    async def execute(
        self,
        command: List[str],
        timeout_seconds: Optional[int] = None,
    ) -> SandboxExecutionResult:
        if self._state != SandboxState.RUNNING:
            raise SandboxError(f"Cannot execute in mock sandbox with state {self._state.value}")

        self._executed_commands.append(command)
        start_time = time.monotonic()
        effective_timeout = timeout_seconds or self._config.timeout_seconds

        # Check for simulated error triggers in command
        cmd_str = " ".join(command)

        if "trigger:timeout" in cmd_str:
            await asyncio.sleep(0.01)
            raw_stdout = ""
            raw_stderr = f"Simulated execution timeout after {effective_timeout}s"
            timed_out = True
            oom_killed = False
            exit_code = 124
        elif "trigger:oom" in cmd_str:
            raw_stdout = ""
            raw_stderr = "Simulated kernel out-of-memory kill (exit 137)"
            timed_out = False
            oom_killed = True
            exit_code = 137
        elif self._command_handler:
            result = self._command_handler(command)
            return result
        else:
            # Default success simulation
            raw_stdout = f"Mock execution succeeded for command: {command}"
            raw_stderr = ""
            timed_out = False
            oom_killed = False
            exit_code = 0

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Output truncation & redaction
        trunc_stdout, trunc_out_flag = truncate_output(raw_stdout, self._config.output_limit_bytes)
        trunc_stderr, trunc_err_flag = truncate_output(raw_stderr, self._config.output_limit_bytes)

        clean_stdout = redact_sandbox_output(trunc_stdout)
        clean_stderr = redact_sandbox_output(trunc_stderr)

        return SandboxExecutionResult(
            exit_code=exit_code,
            stdout=clean_stdout,
            stderr=clean_stderr,
            timed_out=timed_out,
            oom_killed=oom_killed,
            output_truncated=(trunc_out_flag or trunc_err_flag),
            duration_ms=duration_ms,
            peak_memory_bytes=50 * 1024 * 1024,
            cpu_usage_seconds=0.05,
        )

    async def terminate(self) -> None:
        self._state = SandboxState.TERMINATED

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "memory_usage": 52428800,  # 50MB
            "memory_limit": 2147483648,  # 2048MB
            "cpu_percent": 12.5,
            "pids": 4,
        }


class MockSandboxManager(ISandboxManager):
    """
    Simulated manager for test isolation and CI verification.
    """

    def __init__(
        self,
        available: bool = True,
        command_handler: Optional[Callable[[List[str]], SandboxExecutionResult]] = None,
    ) -> None:
        self._available = available
        self._active_sandboxes: Dict[str, MockSandbox] = {}
        self._command_handler = command_handler

    async def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    async def create_sandbox(self, config: SandboxConfig) -> ISandbox:
        # Step 1: Validate security invariants strictly
        validate_sandbox_security_invariants(config)

        cid = f"mock-sbx-{uuid.uuid4().hex[:12]}"
        sandbox = MockSandbox(
            container_id=cid,
            config=config,
            command_handler=self._command_handler,
        )
        self._active_sandboxes[cid] = sandbox
        return sandbox

    async def cleanup_orphans(self, older_than_seconds: int = 600) -> int:
        purged = 0
        for sbx in list(self._active_sandboxes.values()):
            await sbx.terminate()
            purged += 1
        self._active_sandboxes.clear()
        return purged
