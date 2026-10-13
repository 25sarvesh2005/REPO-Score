"""
Adversarial Tests: Sandbox Isolation, Resource Limits, and Buffer Flooding.
Adheres strictly to Phase 14 scope: controlled fixtures only, zero host compromise.
"""

import pytest

from backend.sandbox.exceptions import (
    SandboxSecurityViolationError,
)
from backend.sandbox.models import NetworkPolicy, SandboxConfig
from backend.sandbox.sanitizer import (
    redact_sandbox_output,
    sanitize_environment,
    truncate_output,
)
from backend.sandbox.validator import (
    validate_sandbox_security_invariants,
)


def test_adversarial_output_flooding_truncated():
    """
    Simulate a hostile container process attempting log flooding (e.g., 20MB of output).
    Buffer must be truncated to safe threshold (10MB limit) with explicit truncation marker.
    """
    giant_output = "A" * (15 * 1024 * 1024)  # 15 Megabytes
    truncated, is_truncated = truncate_output(giant_output, max_bytes=10 * 1024 * 1024)

    assert is_truncated is True
    assert len(truncated.encode("utf-8")) <= (10 * 1024 * 1024) + 100
    assert "[TRUNCATED: Maximum step output buffer exceeded]" in truncated


def test_adversarial_secret_leakage_in_flood_output():
    """
    Verify secret redaction occurs even in high-volume outputs.
    """
    payload = "Deployment log:\nghp_1234567890abcdef1234567890abcdef1234\n" * 1000
    sanitized = redact_sandbox_output(payload)

    assert "ghp_1234567890abcdef" not in sanitized
    assert "[REDACTED_GH_TOKEN]" in sanitized


def test_adversarial_environment_injection_sanitization():
    """
    Simulate hostile env vars passed into container attempting to leak host credentials.
    """
    hostile_env = {
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "GITHUB_TOKEN": "ghp_1234567890abcdef1234567890abcdef1234",
        "DATABASE_URL": "postgresql://postgres:secret@localhost:5432/db",
        "NORMAL_VAR": "safe_value",
        "PATH": "/custom/bin:/usr/bin",
    }

    clean_env = sanitize_environment(hostile_env)

    # All sensitive keys stripped by whitelist & blacklist
    assert "AWS_SECRET_ACCESS_KEY" not in clean_env
    assert "GITHUB_TOKEN" not in clean_env
    assert "DATABASE_URL" not in clean_env
    assert "NORMAL_VAR" not in clean_env  # Not in whitelist
    assert clean_env["PATH"] == "/custom/bin:/usr/bin"
    assert clean_env["USER"] == "sandbox"


def test_adversarial_pids_and_memory_quota_validation():
    """
    Verify security validator enforces strict limits on cgroups memory, CPUs, and PIDs.
    """
    # 1. PIDs limit exceeding 256 rejected by validator
    config_pid = SandboxConfig.model_construct(
        image="reposcore/sandbox-python:3.11-slim",
        user="10001:10001",
        read_only_rootfs=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode=NetworkPolicy.NONE,
        memory_limit="2048m",
        cpu_quota=2.0,
        pids_limit=512,
        bind_mounts={},
    )
    with pytest.raises(SandboxSecurityViolationError, match="PID limit"):
        validate_sandbox_security_invariants(config_pid)

    # 2. Memory limit exceeding 2048MB rejected
    config_mem = SandboxConfig(
        image="reposcore/sandbox-python:3.11-slim",
        user="10001:10001",
        read_only_rootfs=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode=NetworkPolicy.NONE,
        memory_limit="4096m",
        cpu_quota=2.0,
        pids_limit=128,
        bind_mounts={},
    )
    with pytest.raises(SandboxSecurityViolationError, match="memory limit"):
        validate_sandbox_security_invariants(config_mem)

    # 3. CPU limit exceeding 2.0 rejected
    config_cpu = SandboxConfig(
        image="reposcore/sandbox-python:3.11-slim",
        user="10001:10001",
        read_only_rootfs=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode=NetworkPolicy.NONE,
        memory_limit="2048m",
        cpu_quota=3.5,
        pids_limit=128,
        bind_mounts={},
    )
    with pytest.raises(SandboxSecurityViolationError, match="CPU quota"):
        validate_sandbox_security_invariants(config_cpu)


def test_adversarial_docker_socket_mount_prohibition():
    """
    Verify mounting /var/run/docker.sock or writable host mounts is strictly prohibited (Prime Directive #4).
    """
    # 1. Docker socket mount forbidden
    config_docker = SandboxConfig(
        image="reposcore/sandbox-python:3.11-slim",
        user="10001:10001",
        read_only_rootfs=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode=NetworkPolicy.NONE,
        memory_limit="2048m",
        cpu_quota=2.0,
        pids_limit=128,
        bind_mounts={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "ro"}},
    )
    with pytest.raises(SandboxSecurityViolationError, match="Docker socket"):
        validate_sandbox_security_invariants(config_docker)

    # 2. Writable host bind mount forbidden
    config_rw = SandboxConfig(
        image="reposcore/sandbox-python:3.11-slim",
        user="10001:10001",
        read_only_rootfs=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode=NetworkPolicy.NONE,
        memory_limit="2048m",
        cpu_quota=2.0,
        pids_limit=128,
        bind_mounts={"/host/source": {"bind": "/workspace/src", "mode": "rw"}},
    )
    with pytest.raises(SandboxSecurityViolationError, match="must be mounted read-only"):
        validate_sandbox_security_invariants(config_rw)
