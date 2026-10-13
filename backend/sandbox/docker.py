"""
Hardened Docker container execution backend.
Programmatically manages ephemeral containers with strict cgroups v2, capability stripping,
and network isolation constraints.
"""

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.sandbox.exceptions import (
    SandboxError,
    SandboxUnavailableError,
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

logger = logging.getLogger(__name__)


class DockerSandbox(ISandbox):
    """
    Active container handle executing commands inside an isolated Docker sandbox.
    """

    def __init__(
        self,
        container_id: str,
        container_name: str,
        config: SandboxConfig,
    ) -> None:
        self._container_id = container_id
        self._container_name = container_name
        self._config = config
        self._state = SandboxState.RUNNING

    @property
    def container_id(self) -> str:
        return self._container_id

    @property
    def state(self) -> SandboxState:
        return self._state

    async def execute(
        self,
        command: list[str],
        timeout_seconds: int | None = None,
    ) -> SandboxExecutionResult:
        """
        Execute command inside the active container via 'docker exec'.
        """
        if self._state != SandboxState.RUNNING:
            raise SandboxError(f"Cannot execute in container with state {self._state.value}")

        effective_timeout = timeout_seconds or self._config.timeout_seconds
        start_time = time.monotonic()

        # Build sanitized execution command
        exec_args = ["docker", "exec", "-i", self._container_name] + command
        process = None
        timed_out = False
        oom_killed = False

        try:
            process = await asyncio.create_subprocess_exec(
                *exec_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=effective_timeout
            )
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace")
            raw_stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0

            # Exit code 137 indicates SIGKILL, typically triggered by kernel OOM killer
            if exit_code == 137:
                oom_killed = True

        except TimeoutError:
            timed_out = True
            exit_code = 124
            raw_stdout = ""
            raw_stderr = f"Command timed out after {effective_timeout} seconds."
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass

        except Exception as exc:
            exit_code = 1
            raw_stdout = ""
            raw_stderr = f"Execution error: {exc}"

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Truncate and redact output
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
        )

    async def terminate(self) -> None:
        """Forcefully purge the container instance."""
        if self._state == SandboxState.TERMINATED:
            return

        self._state = SandboxState.TERMINATED
        try:
            # Force kill and remove container with volumes
            kill_proc = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                "-v",
                self._container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await kill_proc.wait()
        except Exception as exc:
            logger.warning(f"Error terminating container {self._container_name}: {exc}")

    async def get_stats(self) -> dict[str, Any]:
        """Fetch container resource metrics via 'docker stats'."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                self._container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            import json

            parsed = json.loads(stdout_bytes.decode("utf-8").strip())
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}


class DockerSandboxManager(ISandboxManager):
    """
    Production Docker manager implementing ISandboxManager.
    """

    async def is_available(self) -> bool:
        """Check if Docker CLI / Daemon is accessible on the host."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    OFFICIAL_IMAGE_FALLBACKS: dict[str, str] = {
        "reposcore/sandbox-python:3.11-slim": "python:3.11-slim",
        "reposcore/sandbox-node:20-slim": "node:20-slim",
        "reposcore/sandbox-go:1.22-alpine": "golang:1.22-alpine",
        "reposcore/sandbox-rust:1.77-slim": "rust:1.77-slim",
        "reposcore/sandbox-java:21-temurin": "eclipse-temurin:21-jre-alpine",
    }

    async def _image_exists_locally(self, image_name: str) -> bool:
        """Check if image exists in the local Docker daemon image cache."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "image",
                "inspect",
                image_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    async def _resolve_image(self, requested_image: str) -> str:
        """Resolve requested image with graceful fallback to standard official library images."""
        if await self._image_exists_locally(requested_image):
            return requested_image

        fallback = self.OFFICIAL_IMAGE_FALLBACKS.get(requested_image)
        if fallback:
            if await self._image_exists_locally(fallback):
                logger.info(
                    f"Custom sandbox image '{requested_image}' not found locally. Using cached fallback '{fallback}'."
                )
                return fallback
            logger.info(
                f"Custom image '{requested_image}' not found. Defaulting to official base image '{fallback}'."
            )
            return fallback

        return requested_image

    async def create_sandbox(self, config: SandboxConfig) -> ISandbox:
        """
        Validate security invariants, launch hardened Docker container, and return handle.
        """
        # Step 1: Validate security invariants (strict non-root, capability stripping, socket isolation)
        validate_sandbox_security_invariants(config)

        # Step 2: Check runtime availability
        if not await self.is_available():
            raise SandboxUnavailableError(
                "Docker daemon is not running or accessible. Host execution fallback is strictly prohibited."
            )

        resolved_image = await self._resolve_image(config.image)
        container_name = f"reposcore-sbx-{uuid.uuid4().hex[:12]}"
        sanitized_env = sanitize_environment(config.environment)

        # Step 3: Build hardened docker run arguments
        run_args = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            f"--user={config.user}",
            "--read-only",
            f"--memory={config.memory_limit}",
            f"--memory-swap={config.memory_swap}",
            f"--cpus={config.cpu_quota}",
            f"--pids-limit={config.pids_limit}",
            f"--network={config.network_mode.value}",
            f"--workdir={config.workdir}",
        ]

        # Kernel capabilities
        for cap in config.cap_drop:
            run_args.append(f"--cap-drop={cap}")

        # Security options
        for opt in config.security_opt:
            run_args.append(f"--security-opt={opt}")

        # tmpfs mounts
        for dest, flags in config.tmpfs_mounts.items():
            run_args.append(f"--tmpfs={dest}:{flags}")

        # Bind mounts
        for host_src, spec in config.bind_mounts.items():
            bind_dest = spec.get("bind", host_src)
            mode = spec.get("mode", "ro")
            run_args.append(f"-v={host_src}:{bind_dest}:{mode}")

        # Environment variables
        for k, v in sanitized_env.items():
            run_args.append(f"-e={k}={v}")

        # Labels
        run_args.append("--label=reposcore.managed=true")
        run_args.append(f"--label=reposcore.created_at={datetime.now(UTC).isoformat()}")
        for lk, lv in config.labels.items():
            run_args.append(f"--label={lk}={lv}")

        run_args.append(resolved_image)

        # Tail sleep to keep container alive for interactive command execution
        run_args.extend(["tail", "-f", "/dev/null"])

        # Step 4: Launch container
        proc = await asyncio.create_subprocess_exec(
            *run_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=45)

        # If custom image failed to spawn, try official fallback image as last resort
        if proc.returncode != 0 and resolved_image != self.OFFICIAL_IMAGE_FALLBACKS.get(
            config.image
        ):
            fallback_img = self.OFFICIAL_IMAGE_FALLBACKS.get(config.image)
            if fallback_img:
                logger.warning(
                    f"Spawn with '{resolved_image}' failed. Retrying with fallback '{fallback_img}'..."
                )
                run_args[-2] = fallback_img
                proc = await asyncio.create_subprocess_exec(
                    *run_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=45)

        if proc.returncode != 0:
            err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
            raise SandboxError(f"Failed to spawn Docker sandbox: {err_msg}")

        container_id = stdout_bytes.decode("utf-8").strip()[:12]
        return DockerSandbox(
            container_id=container_id,
            container_name=container_name,
            config=config,
        )

    async def cleanup_orphans(self, older_than_seconds: int = 600) -> int:
        """Purge dangling containers labeled with reposcore.managed=true."""
        if not await self.is_available():
            return 0

        purged_count = 0
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "ps",
                "-a",
                "--filter",
                "label=reposcore.managed=true",
                "--format",
                "{{.ID}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            cids = stdout_bytes.decode("utf-8").strip().splitlines()
            for cid in cids:
                if cid:
                    rm_proc = await asyncio.create_subprocess_exec(
                        "docker",
                        "rm",
                        "-f",
                        "-v",
                        cid.strip(),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await rm_proc.wait()
                    purged_count += 1
        except Exception as exc:
            logger.warning(f"Error during orphan container cleanup: {exc}")

        return purged_count
