"""
Unit tests for sandbox security invariants validation.
"""

import pytest
from pydantic import ValidationError

from backend.sandbox.exceptions import SandboxSecurityViolationError
from backend.sandbox.models import NetworkPolicy, SandboxConfig
from backend.sandbox.validator import (
    parse_memory_mb,
    validate_sandbox_security_invariants,
)


@pytest.fixture
def valid_config() -> SandboxConfig:
    return SandboxConfig(
        image="reposcore/sandbox-python:3.11-slim",
        user="10001:10001",
        read_only_rootfs=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode=NetworkPolicy.NONE,
        memory_limit="2048m",
        memory_swap="2048m",
        cpu_quota=2.0,
        pids_limit=128,
        tmpfs_mounts={"/workspace/build": "rw,nosuid,nodev,size=1024m"},
        bind_mounts={"/var/reposcore/snapshots/test": {"bind": "/workspace/src", "mode": "ro"}},
    )


def test_valid_config_passes_validation(valid_config: SandboxConfig) -> None:
    # Must not raise
    validate_sandbox_security_invariants(valid_config)


@pytest.mark.parametrize("invalid_user", ["0", "root", "0:0", "root:root"])
def test_reject_root_user(valid_config: SandboxConfig, invalid_user: str) -> None:
    valid_config.user = invalid_user
    with pytest.raises(SandboxSecurityViolationError, match="root"):
        validate_sandbox_security_invariants(valid_config)


def test_reject_missing_cap_drop_all(valid_config: SandboxConfig) -> None:
    valid_config.cap_drop = ["NET_RAW"]
    with pytest.raises(SandboxSecurityViolationError, match="cap_drop"):
        validate_sandbox_security_invariants(valid_config)


def test_reject_missing_no_new_privileges(valid_config: SandboxConfig) -> None:
    valid_config.security_opt = []
    with pytest.raises(SandboxSecurityViolationError, match="no-new-privileges"):
        validate_sandbox_security_invariants(valid_config)


def test_reject_writable_root_filesystem(valid_config: SandboxConfig) -> None:
    valid_config.read_only_rootfs = False
    with pytest.raises(SandboxSecurityViolationError, match="read-only"):
        validate_sandbox_security_invariants(valid_config)


@pytest.mark.parametrize("excessive_memory", ["3000m", "4g", "4096m"])
def test_reject_excessive_memory(valid_config: SandboxConfig, excessive_memory: str) -> None:
    valid_config.memory_limit = excessive_memory
    with pytest.raises(SandboxSecurityViolationError, match="memory"):
        validate_sandbox_security_invariants(valid_config)


def test_reject_excessive_cpu_quota() -> None:
    # Validates Pydantic or security invariant validator
    with pytest.raises(ValidationError):
        SandboxConfig(
            image="test",
            cpu_quota=5.0,  # exceeds Pydantic le=4.0
        )


def test_reject_excessive_pids(valid_config: SandboxConfig) -> None:
    # Pydantic allows up to 256, test 260
    with pytest.raises(ValidationError):
        SandboxConfig(
            image="test",
            pids_limit=300,
        )


@pytest.mark.parametrize(
    "malicious_mount",
    [
        "/var/run/docker.sock",
        "/var/run/docker.sock.raw",
        "//./pipe/docker_engine",
        "C:/ProgramData/Docker/docker.sock",
    ],
)
def test_strictly_forbid_docker_socket_mount(
    valid_config: SandboxConfig, malicious_mount: str
) -> None:
    valid_config.bind_mounts = {malicious_mount: {"bind": "/workspace/docker.sock", "mode": "ro"}}
    with pytest.raises(SandboxSecurityViolationError, match="Docker socket"):
        validate_sandbox_security_invariants(valid_config)


def test_reject_writable_bind_mount(valid_config: SandboxConfig) -> None:
    valid_config.bind_mounts = {
        "/var/reposcore/snapshots/test": {"bind": "/workspace/src", "mode": "rw"}
    }
    with pytest.raises(SandboxSecurityViolationError, match="read-only"):
        validate_sandbox_security_invariants(valid_config)


def test_parse_memory_mb() -> None:
    assert parse_memory_mb("2048m") == 2048
    assert parse_memory_mb("2g") == 2048
    assert parse_memory_mb("512MB") == 512
