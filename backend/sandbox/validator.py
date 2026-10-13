"""
Security Invariants Validator for Ephemeral Sandbox Configurations.
Strictly validates adherence to ADR-002, SANDBOX_SECURITY_SPEC, and AGENTS Prime Directives.
"""

import re

from backend.sandbox.exceptions import SandboxSecurityViolationError
from backend.sandbox.models import SandboxConfig


def parse_memory_mb(mem_str: str) -> int:
    """Parse memory string (e.g. '2048m', '2g', '512m') into integer megabytes."""
    match = re.match(r"^(\d+)\s*([mMgGkK]?)[bB]?$", mem_str.strip())
    if not match:
        raise SandboxSecurityViolationError(f"Invalid memory limit format: '{mem_str}'")
    val, unit = int(match.group(1)), match.group(2).lower()
    if unit == "g":
        return val * 1024
    if unit == "k":
        return max(1, val // 1024)
    return val  # Default megabytes


def validate_sandbox_security_invariants(config: SandboxConfig) -> None:
    """
    Validate that SandboxConfig strictly adheres to container security mandates.

    Invariants Enforced:
    1. Root execution is prohibited (must not be '0', 'root', or '0:0').
    2. Capabilities must be completely stripped ('cap_drop' contains 'ALL').
    3. Privilege escalation must be disabled ('no-new-privileges:true').
    4. Root filesystem must be read-only ('read_only_rootfs=True').
    5. Memory ceiling must not exceed 2048MB.
    6. CPU quota must not exceed 2.0 cores.
    7. PID quota must not exceed 256 processes.
    8. Docker socket (/var/run/docker.sock) must NEVER be mounted into the container.
    9. Host repository bind mounts must be read-only ('mode': 'ro').
    """
    # 1. Non-root user check
    user = (config.user or "").strip().lower()
    if user in {"0", "root", "0:0", "root:root"}:
        raise SandboxSecurityViolationError(
            f"Container execution as root ('{config.user}') is strictly prohibited."
        )

    # 2. Linux capabilities dropped
    if not config.cap_drop or "ALL" not in [c.upper() for c in config.cap_drop]:
        raise SandboxSecurityViolationError(
            "Sandbox configuration must include 'cap_drop': ['ALL'] to strip all Linux capabilities."
        )

    # 3. Privilege escalation prohibited
    has_no_new_privs = any("no-new-privileges:true" in opt.lower() for opt in config.security_opt)
    if not has_no_new_privs:
        raise SandboxSecurityViolationError(
            "Sandbox configuration must enforce '--security-opt no-new-privileges:true'."
        )

    # 4. Read-only root filesystem
    if not config.read_only_rootfs:
        raise SandboxSecurityViolationError(
            "Root filesystem must be read-only ('read_only_rootfs=True')."
        )

    # 5. Memory quota ceiling
    mem_mb = parse_memory_mb(config.memory_limit)
    if mem_mb > 2048:
        raise SandboxSecurityViolationError(
            f"Requested memory limit '{config.memory_limit}' ({mem_mb}MB) exceeds maximum ceiling of 2048MB."
        )

    # 6. CPU quota ceiling
    if config.cpu_quota > 2.0:
        raise SandboxSecurityViolationError(
            f"Requested CPU quota {config.cpu_quota} exceeds maximum ceiling of 2.0 cores."
        )

    # 7. PID process limit
    if config.pids_limit > 256:
        raise SandboxSecurityViolationError(
            f"Requested PID limit {config.pids_limit} exceeds maximum ceiling of 256 processes."
        )

    # 8 & 9. Mount checks
    for host_path, mount_spec in config.bind_mounts.items():
        # NEVER mount docker.sock
        norm_host = host_path.replace("\\", "/").lower()
        if "docker.sock" in norm_host or "docker_engine" in norm_host:
            raise SandboxSecurityViolationError(
                f"Mounting the Docker socket ('{host_path}') into an untrusted container is strictly prohibited!"
            )

        container_dest = mount_spec.get("bind", "").replace("\\", "/").lower()
        if "docker.sock" in container_dest:
            raise SandboxSecurityViolationError(
                f"Mounting to container path '{container_dest}' is strictly prohibited!"
            )

        # Host bind mounts must be read-only
        mount_mode = mount_spec.get("mode", "ro").lower()
        if mount_mode != "ro":
            raise SandboxSecurityViolationError(
                f"Host bind mount '{host_path}' must be mounted read-only ('mode': 'ro'). Mode '{mount_mode}' is rejected."
            )
