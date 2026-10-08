# ADR-002: Docker Sandbox Architecture

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Security & Infrastructure Architecture Team  
> **Consulted:** Core Systems Team  

---

## Context
RepoScore must build, start, and evaluate arbitrary code from public Git repositories. Because submitted repositories are inherently untrusted and may contain malicious code (fork bombs, cryptominers, reverse shells, filesystem wipers), execution must be rigidly constrained. We need an execution sandbox that provides strong isolation, fine-grained resource limits, zero host impact, and zero-cost local developer reproducibility.

---

## Decision
We select **Docker Engine containerization with hardened security profiles** as the baseline execution sandbox mechanism, managed programmatically via the Docker Engine API.
- All untrusted repository commands execute inside ephemeral, single-use containers.
- Hard constraints enforced:
  - User namespaces: Non-root user `uid: 10001` / `gid: 10001`.
  - Kernel capabilities: 100% stripped (`--cap-drop=ALL`).
  - Privilege escalation blocked: `no-new-privileges:true`.
  - cgroups v2 limits: 2048MB RAM, 2.0 CPU cores, 256 PIDs.
  - Storage: Read-only root filesystem with ephemeral memory-backed `tmpfs` mounts.
  - Network: Staged network policy (restricted egress proxy during build; completely disabled `--network none` during runtime probing).
- The `ISandboxManager` interface will abstract container lifecycle operations, allowing future drop-in upgrades to gVisor (`runsc`) or Firecracker microVMs.

---

## Alternatives Considered
1. **Host-level Subprocess Execution (`subprocess.Popen` with chroot)**:
   - *Pros*: Fast startup.
   - *Cons*: Catastrophic security failure. Any malicious binary or script could escape and wipe or compromise the host machine.
2. **Full Hardware Virtual Machines (QEMU/KVM)**:
   - *Pros*: Maximum virtualization isolation.
   - *Cons*: Heavy memory overhead, slow boot times (10-30s), complex orchestration for developer machines.
3. **gVisor (`runsc`) as initial baseline**:
   - *Pros*: Strongest user-space syscall interception.
   - *Cons*: Requires Linux host with nested virtualization or root daemon config; difficult for local development across macOS/Windows Docker Desktop. Retained as an optional production runtime adapter.

---

## Consequences
- **Positive**:
  - Ubiquitous local support: Works out-of-the-box on developer workstations with Docker.
  - Instant startup: Containers boot in <500ms using pre-built base runtime images.
  - Granular resource metrics extracted via Docker cgroups stats API.
- **Negative**:
  - Docker daemon is a shared host resource; requires strict auditing to ensure `/var/run/docker.sock` is never exposed to untrusted containers.

---

## Security Impact
- Eliminates accidental host filesystem corruption or credential leakage.
- Stripping all Linux capabilities prevents untrusted binaries from using raw sockets, mounting filesystems, or interacting with host hardware.

---

## Operational Impact
- Requires Docker daemon installed on worker nodes.
- Ephemeral containers must be rigorously swept and pruned to avoid dangling container leaks.
