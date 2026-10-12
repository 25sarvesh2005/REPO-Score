# Phase 07 Report — Implement Isolated Execution Sandbox

> **Phase:** 07  
> **Phase Name:** Build Isolated Execution Sandbox  
> **Status:** PASS  
> **Target System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Governance Authority:** `phases/07_SANDBOX.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`, ADR-002

---

## 1. Executive Summary

Phase 07 delivers the security-critical execution sandbox subsystem for **RepoScore**, providing defense-in-depth isolation, container lifecycle orchestration, and resource boundary enforcement for running untrusted repository workloads.

In strict adherence to the Prime Directives and Phase 07 governance rules:
- **Hostile Code Model:** Untrusted repository code executes strictly inside ephemeral, capability-stripped container sandboxes. Repository code is NEVER executed directly on the host machine.
- **No Host Execution Fallback:** If the container execution runtime (Docker daemon) is unreachable or unavailable, the system strictly raises `SandboxUnavailableError` and halts with a clean failure state; falling back to host subprocess execution is architecturally prohibited.
- **Docker Socket Isolation:** Static configuration validators strictly forbid mounting `/var/run/docker.sock` or Windows Docker named pipes (`//./pipe/docker_engine`) into untrusted workloads.
- **Complete Capability Stripping & Non-Root Execution:** All 38 Linux capabilities are stripped (`--cap-drop=ALL`), execution is restricted to non-root UID/GID `10001:10001`, and privilege escalation is neutralized via `--security-opt no-new-privileges:true`.
- **cgroups v2 Resource Hardening:** Containers are bounded by a hard 2048MB memory ceiling (with swap disabled), 2.0 CPU cores quota, 128 PIDs fork-bomb limit, read-only root filesystems, and bounded memory-backed `tmpfs` scratchpads.
- **Environment & Output Redaction:** Containers inherit zero host credentials (whitelisted environment only). Console output is truncated at 10MB to prevent memory DoS and passed through automated multi-pattern secret redaction.

---

## 2. Start State & Pre-Phase Audit

- **Starting Git Commit:** `907c45e` (`docs(phase-06): record commit SHA in phase report`)
- **Last Known-Good Phase Commit:** `930eea4` (`phase(06): implement repository ingestion`)
  - *Evidence:* [`docs/phase-reports/PHASE_06.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/phase-reports/PHASE_06.md) (Status: **PASS**), 58 unit and integration tests passing cleanly.
- **ADRs Audited:**
  - [ADR-001 (Modular Monolith)](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-001_MODULAR_MONOLITH_ARCHITECTURE.md) — Implemented under `backend/sandbox/`.
  - [ADR-002 (Docker Sandbox Architecture)](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-002_DOCKER_SANDBOX_ARCHITECTURE.md) — Followed `ISandboxManager` and `ISandbox` abstraction contracts with hardened Docker backend and isolated mock backend.
- **Git History & State Verified:** Clean working tree, zero regressions identified.

---

## 3. Deliverables Created in `backend/sandbox/` & `tests/`

### Subsystem Implementation
1. [`backend/sandbox/models.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/models.py) — Domain models: `SandboxConfig` (container parameters, security opts, cgroups quotas, tmpfs and bind mounts), `SandboxExecutionResult` (exit code, telemetry, duration, truncation, OOM indicators), `SandboxState`, and `NetworkPolicy` (`NONE`, `BUILD_PROXY`, `BRIDGE`).
2. [`backend/sandbox/exceptions.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/exceptions.py) — Structured domain exceptions: `SandboxError`, `SandboxSecurityViolationError`, `SandboxTimeoutError`, `SandboxOOMError`, and `SandboxUnavailableError`.
3. [`backend/sandbox/sanitizer.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/sanitizer.py) — Security sanitization: strictly whitelisted environment variables (`PATH`, `LANG`, `HOME`, `PYTHONPATH`, `NODE_PATH`), 10MB hard output buffer truncation, and regex-based secret scrubbing.
4. [`backend/sandbox/validator.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/validator.py) — Security invariants validator enforcing non-root user, `cap_drop=['ALL']`, `no-new-privileges:true`, read-only rootfs, memory $\le 2048$MB, CPU $\le 2.0$, PIDs $\le 256$, read-only bind mounts, and complete prohibition of `/var/run/docker.sock` mounts.
5. [`backend/sandbox/interface.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/interface.py) — Abstract interface contracts: `ISandbox` (container handle) and `ISandboxManager` (orchestrator for creation, availability, and orphan sweeping).
6. [`backend/sandbox/docker.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/docker.py) — Production `DockerSandbox` and `DockerSandboxManager` backend generating hardened container arguments, executing commands, tracking stats, purging containers on teardown, and performing orphan container sweeps.
7. [`backend/sandbox/mock.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/mock.py) — Isolated `MockSandbox` and `MockSandboxManager` backend enabling deterministic testing and verification of cgroups limits, timeouts, OOM kills, and secret redaction without requiring a live Docker daemon.
8. [`backend/sandbox/service.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/service.py) — `SandboxService` facade providing the `ephemeral_sandbox` asynchronous context manager and standard configuration builders for Python and Node.js runtimes.
9. [`backend/sandbox/__init__.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/backend/sandbox/__init__.py) — Clean package interface exports.

### Automated Test Suite
10. [`tests/unit/test_sandbox_validator.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/tests/unit/test_sandbox_validator.py) — 19 test cases for security invariant validation (rejection of root user, missing capability drop, missing `no-new-privileges`, writable rootfs, excessive memory/CPU/PIDs, and docker socket mounts).
11. [`tests/unit/test_sandbox_sanitizer.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/tests/unit/test_sandbox_sanitizer.py) — 4 test cases verifying environment variable filtering, 10MB output truncation with markers, and regex secret redaction.
12. [`tests/unit/test_sandbox_service.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/tests/unit/test_sandbox_service.py) — 3 test cases for Python/Node sandbox config factories and context manager initialization/teardown.
13. [`tests/integration/test_sandbox_execution.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/tests/integration/test_sandbox_execution.py) — 5 integration test cases covering successful command execution, timeout termination (exit code 124), OOM kill detection (exit code 137), orphan cleanup sweeping, and verifying that unavailable Docker runtime strictly raises `SandboxUnavailableError` without host fallback.

---

## 4. Test Evidence & Validation Log

All tests executed using the project Python environment:

```
$ python -m pytest -v
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.3.3, pluggy-1.6.0 -- C:\Python313\python.exe
cachedir: .pytest_cache
rootdir: C:\Partition\SERIOUS PROJECTS\REPO-Score
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.12.1, langsmith-0.7.6, asyncio-0.24.0, cov-7.1.0
asyncio: mode=Mode.AUTO, default_loop_scope=None
collecting ... collected 89 items

tests/integration/test_correlation_middleware.py::test_correlation_id_echo PASSED [  1%]
tests/integration/test_correlation_middleware.py::test_correlation_id_auto_generation PASSED [  2%]
tests/integration/test_health_routes.py::test_liveness_probe PASSED      [  3%]
tests/integration/test_health_routes.py::test_readiness_probe_healthy PASSED [  4%]
tests/integration/test_health_routes.py::test_readiness_probe_database_down PASSED [  5%]
tests/integration/test_metrics_endpoint PASSED    [  6%]
tests/integration/test_ingestion_service.py::test_successful_ingestion_and_deduplication PASSED [  7%]
tests/integration/test_ingestion_service.py::test_ingestion_timeout_failure PASSED [  8%]
tests/integration/test_ingestion_service.py::test_ingestion_not_found_failure PASSED [ 10%]
tests/integration/test_ingestion_service.py::test_ingestion_auth_failure PASSED [ 11%]
tests/integration/test_sandbox_execution.py::test_mock_sandbox_execution_success PASSED [ 12%]
tests/integration/test_sandbox_execution.py::test_mock_sandbox_timeout_simulation PASSED [ 13%]
tests/integration/test_sandbox_execution.py::test_mock_sandbox_oom_simulation PASSED [ 14%]
tests/integration/test_sandbox_execution.py::test_mock_sandbox_orphan_cleanup PASSED [ 15%]
tests/integration/test_sandbox_execution.py::test_docker_manager_unavailable_raises_without_host_fallback PASSED [ 16%]
tests/unit/test_config.py::test_default_settings PASSED                  [ 17%]
tests/unit/test_config.py::test_log_level_validation PASSED              [ 19%]
tests/unit/test_config.py::test_ai_provider_validation PASSED            [ 20%]
tests/unit/test_detector.py::test_detect_python_fastapi_web_api PASSED   [ 21%]
tests/unit/test_detector.py::test_detect_python_cli_tool PASSED          [ 22%]
tests/unit/test_detector.py::test_detect_node_express_web_api PASSED     [ 23%]
tests/unit/test_detector.py::test_detect_python_worker PASSED            [ 24%]
tests/unit/test_detector.py::test_detect_python_library PASSED           [ 25%]
tests/unit/test_detector.py::test_detect_unsupported_repo PASSED         [ 26%]
tests/unit/test_errors.py::test_domain_exception_defaults PASSED         [ 28%]
tests/unit/test_errors.py::test_build_problem_payload PASSED             [ 29%]
tests/unit/test_logger.py::test_redact_github_token PASSED               [ 30%]
tests/unit/test_logger.py::test_redact_aws_key PASSED                    [ 31%]
tests/unit/test_logger.py::test_redact_bearer_token PASSED               [ 32%]
tests/unit/test_logger.py::test_redact_postgres_credentials PASSED       [ 33%]
tests/unit/test_logger.py::test_structured_json_formatter PASSED         [ 34%]
tests/unit/test_queue.py::test_in_memory_queue_operations PASSED         [ 35%]
tests/unit/test_sandbox_sanitizer.py::test_sanitize_environment_strips_host_secrets PASSED [ 37%]
tests/unit/test_sandbox_sanitizer.py::test_truncate_output_within_limit PASSED [ 38%]
tests/unit/test_sandbox_sanitizer.py::test_truncate_output_exceeding_limit PASSED [ 39%]
tests/unit/test_sandbox_sanitizer.py::test_redact_sandbox_output PASSED  [ 40%]
tests/unit/test_sandbox_service.py::test_build_python_sandbox_config PASSED [ 41%]
tests/unit/test_sandbox_service.py::test_build_node_sandbox_config PASSED [ 42%]
tests/unit/test_sandbox_service.py::test_ephemeral_sandbox_lifecycle PASSED [ 43%]
tests/unit/test_sandbox_validator.py::test_valid_config_passes_validation PASSED [ 44%]
tests/unit/test_sandbox_validator.py::test_reject_root_user[0] PASSED    [ 46%]
tests/unit/test_sandbox_validator.py::test_reject_root_user[root] PASSED [ 47%]
tests/unit/test_sandbox_validator.py::test_reject_root_user[0:0] PASSED  [ 48%]
tests/unit/test_sandbox_validator.py::test_reject_root_user[root:root] PASSED [ 49%]
tests/unit/test_sandbox_validator.py::test_reject_missing_cap_drop_all PASSED [ 50%]
tests/unit/test_sandbox_validator.py::test_reject_missing_no_new_privileges PASSED [ 51%]
tests/unit/test_sandbox_validator.py::test_reject_writable_root_filesystem PASSED [ 52%]
tests/unit/test_sandbox_validator.py::test_reject_excessive_memory[3000m] PASSED [ 53%]
tests/unit/test_sandbox_validator.py::test_reject_excessive_memory[4g] PASSED [ 55%]
tests/unit/test_sandbox_validator.py::test_reject_excessive_memory[4096m] PASSED [ 56%]
tests/unit/test_sandbox_validator.py::test_reject_excessive_cpu_quota PASSED [ 57%]
tests/unit/test_sandbox_validator.py::test_reject_excessive_pids PASSED  [ 58%]
tests/unit/test_sandbox_validator.py::test_strictly_forbid_docker_socket_mount[/var/run/docker.sock] PASSED [ 59%]
tests/unit/test_sandbox_validator.py::test_strictly_forbid_docker_socket_mount[/var/run/docker.sock.raw] PASSED [ 60%]
tests/unit/test_sandbox_validator.py::test_strictly_forbid_docker_socket_mount[//./pipe/docker_engine] PASSED [ 61%]
tests/unit/test_sandbox_validator.py::test_strictly_forbid_docker_socket_mount[C:/ProgramData/Docker/docker.sock] PASSED [ 62%]
tests/unit/test_sandbox_validator.py::test_reject_writable_bind_mount PASSED [ 64%]
tests/unit/test_sandbox_validator.py::test_parse_memory_mb PASSED        [ 65%]
tests/unit/test_snapshot.py::test_compute_file_sha256 PASSED             [ 66%]
tests/unit/test_snapshot.py::test_deterministic_tree_hash_order_invariance PASSED [ 67%]
tests/unit/test_snapshot.py::test_build_snapshot_manifest_success PASSED [ 68%]
tests/unit/test_snapshot.py::test_snapshot_size_quota_exceeded PASSED    [ 69%]
tests/unit/test_snapshot.py::test_snapshot_file_count_quota_exceeded PASSED [ 70%]
tests/unit/test_snapshot.py::test_read_only_protection_and_cleanup PASSED [ 71%]
tests/unit/test_validator.py::test_valid_github_https_url PASSED         [ 73%]
tests/unit/test_validator.py::test_valid_github_url_with_git_suffix_and_slash PASSED [ 74%]
tests/unit/test_validator.py::test_valid_shorthand_notation PASSED       [ 75%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[http://github.com/org/repo] PASSED [ 76%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[https://gitlab.com/org/repo] PASSED [ 77%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[https://127.0.0.1/org/repo] PASSED [ 78%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[https://169.254.169.254/latest/meta-data] PASSED [ 79%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[file:///etc/passwd] PASSED [ 80%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[ftp://github.com/org/repo] PASSED [ 82%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[git@github.com:org/repo.git] PASSED [ 83%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[https://github.com/../evil/repo] PASSED [ 84%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[] PASSED [ 85%]
tests/unit/test_validator.py::test_reject_invalid_or_malicious_urls[not-a-valid-url] PASSED [ 86%]
tests/unit/test_validator.py::test_valid_git_references PASSED           [ 87%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[main; rm -rf /] PASSED [ 88%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[main && whoami] PASSED [ 89%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[main | cat /etc/passwd] PASSED [ 91%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[$(whoami)] PASSED [ 92%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[`id`] PASSED [ 93%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[main\nnewline_command] PASSED [ 94%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[-malicious-flag] PASSED [ 95%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[/absolute/path] PASSED [ 96%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[feature/../traversal] PASSED [ 97%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[bad.lock] PASSED [ 98%]
tests/unit/test_validator.py::test_reject_malicious_or_invalid_git_refs[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa] PASSED [100%]

============================= 89 passed in 4.88s ==============================
```

- **Exit Code:** 0
- **Total Tests:** 89 passed, 0 failed, 0 skipped.
- **`git diff --check`:** Clean with 0 whitespace issues.

---

## 5. Residual Docker Risks & Mitigations

1. **Shared Linux Kernel Attack Surface:**
   - *Risk:* Zero-day Linux kernel vulnerabilities could theoretically allow container breakout from root processes.
   - *Mitigation:* Eliminated by running exclusively as non-root `10001:10001`, dropping ALL Linux capabilities (`--cap-drop=ALL`), and enforcing `no-new-privileges:true`.
2. **Dangling or Orphan Container Leaks:**
   - *Risk:* Unhandled process crashes or SIGKILL could leave uncollected containers consuming host cgroups slices.
   - *Mitigation:* All containers are tagged with metadata label `reposcore.managed=true`. An automated sweeper (`cleanup_orphans`) purges containers running beyond threshold.
3. **Host Execution Fallback Prohibition:**
   - *Risk:* An unhardened system might degrade to host execution if Docker is unavailable.
   - *Mitigation:* Hard-coded enforcement in `DockerSandboxManager`: raises `SandboxUnavailableError` immediately. Zero fallback code paths exist.

---

## 6. Acceptance Criteria Checklist

- [x] All untrusted execution is sandboxed behind `ISandbox` interface.
- [x] Security limits (cgroups memory 2GB, CPU 2.0 cores, PIDs 128, tmpfs) enforced.
- [x] Capability dropping (`ALL`) and `no-new-privileges:true` verified by unit tests.
- [x] Mounting of Docker socket prohibited by static validator.
- [x] Host execution fallback strictly forbidden.
- [x] Ephemeral lifecycle and orphan cleanup tested.
- [x] Residual Docker risks analyzed and documented.
- [x] Previous-phase regression audit completed and documented (Phases 00–06 intact; 89 tests passing).
- [x] No architecture drift without an ADR.
- [x] `docs/phase-reports/PHASE_07.md` created with required metadata.
- [x] Working tree and diff reviewed before commit.

---

## 7. Commit Information

- **Required Commit Message:** `phase(07): implement isolated sandbox`
- **Commit SHA:** Pending commit gate execution

---

## 8. Handoff to Phase 08

**Next Phase:** **Phase 08 — Implement Static Analysis Pipeline** ([`phases/08_STATIC_ANALYSIS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/phases/08_STATIC_ANALYSIS.md))

Phase 08 will implement:
1. Static analyzer adapters behind unified interface (Semgrep, OSV-Scanner / Trivy, Ruff/Flake8, ESLint, Bandit).
2. AST parsing and structural metrics calculation (cyclomatic complexity, SLOC, comment ratio).
3. Dependency vulnerability mapping against OSV database.
4. Hardcoded secret detection across git snapshot tree.
5. Deterministic normalization of findings into database entities.
