"""
Domain models and configuration schemas for container sandbox isolation.
"""

from enum import Enum

from pydantic import BaseModel, Field


class NetworkPolicy(str, Enum):
    """Network egress isolation tier."""

    NONE = "none"  # Absolute severance: loopback only (127.0.0.1)
    BUILD_PROXY = "build-proxy"  # Egress restricted strictly to whitelisted package registries
    BRIDGE = "bridge"  # Standard Docker bridge (restricted to testing/internal networks)


class SandboxState(str, Enum):
    """Lifecycle status of an ephemeral sandbox instance."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


class SandboxConfig(BaseModel):
    """
    Hardened container configuration enforcing layered security constraints.
    """

    image: str = Field(
        ..., description="Docker base image tag (e.g., reposcore/sandbox-python:3.11-slim)"
    )
    command: list[str] | None = Field(
        default=None, description="Initial command or entrypoint override"
    )
    workdir: str = Field(default="/workspace/build", description="Container working directory")
    user: str = Field(default="10001:10001", description="Non-root user UID:GID")
    read_only_rootfs: bool = Field(
        default=True, description="Enforce read-only root filesystem (--read-only)"
    )
    cap_drop: list[str] = Field(
        default_factory=lambda: ["ALL"], description="Kernel capabilities to drop"
    )
    security_opt: list[str] = Field(
        default_factory=lambda: ["no-new-privileges:true"],
        description="Security options (e.g. no-new-privileges)",
    )
    network_mode: NetworkPolicy = Field(
        default=NetworkPolicy.NONE, description="Network egress policy"
    )
    memory_limit: str = Field(default="2048m", description="Hard memory quota ceiling")
    memory_swap: str = Field(
        default="2048m", description="Memory swap quota (equals memory to disable swap)"
    )
    cpu_quota: float = Field(default=2.0, ge=0.1, le=4.0, description="CPU cores quota")
    pids_limit: int = Field(default=128, ge=16, le=256, description="PID process count ceiling")
    tmpfs_mounts: dict[str, str] = Field(
        default_factory=lambda: {
            "/workspace/build": "rw,nosuid,nodev,size=1024m",
            "/tmp": "rw,nosuid,nodev,size=256m",
        },
        description="Memory-backed ephemeral scratchpad mounts",
    )
    bind_mounts: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Host bind mounts: {host_path: {'bind': container_path, 'mode': 'ro'}}",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Explicitly whitelisted environment variables",
    )
    timeout_seconds: int = Field(
        default=60, ge=1, le=600, description="Execution timeout in seconds"
    )
    output_limit_bytes: int = Field(
        default=10 * 1024 * 1024, description="Max stdout/stderr buffer size (10MB)"
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Metadata labels for auditability and orphan tracking",
    )


class SandboxExecutionResult(BaseModel):
    """Telemetry and outcome of a command executed inside a sandbox."""

    exit_code: int = Field(..., description="Process exit code")
    stdout: str = Field(default="", description="Sanitized and truncated standard output")
    stderr: str = Field(default="", description="Sanitized and truncated standard error")
    timed_out: bool = Field(
        default=False, description="True if process was killed due to execution timeout"
    )
    oom_killed: bool = Field(
        default=False, description="True if process was terminated by kernel OOM killer"
    )
    output_truncated: bool = Field(
        default=False, description="True if log output exceeded buffer limit"
    )
    duration_ms: int = Field(default=0, description="Command execution latency in milliseconds")
    peak_memory_bytes: int | None = Field(default=None, description="Peak memory usage in bytes")
    cpu_usage_seconds: float | None = Field(
        default=None, description="Total CPU time consumed in seconds"
    )
