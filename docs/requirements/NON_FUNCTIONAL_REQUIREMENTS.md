# Non-Functional Requirements Specification (NFR)

> **Document:** `NON_FUNCTIONAL_REQUIREMENTS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Requirements Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. Domain Overview

The Non-Functional Requirements define the operational qualities, performance boundaries, reliability guarantees, maintainability standards, and systemic constraints of RepoScore.

In strict compliance with Phase 01 rules, performance thresholds that have not been validated through empirical testing are marked:
> `TBD — benchmark required`

---

## 2. Security & Isolation

### NFR-001: Zero Host Contamination
- **Priority:** P0
- **Category:** Security Boundary
- **Description:** Untrusted repository code, build commands, and test suites MUST NOT execute directly on the host operating system under any circumstance. All execution must occur inside isolated Docker containers.
- **Verification:** Security audit and adversarial breakout suite (`tests/security/test_sandbox_isolation.py`).

### NFR-002: Least Privilege Container Execution
- **Priority:** P0
- **Category:** Security Boundary
- **Description:** Sandbox containers MUST execute as an unprivileged, non-root user (UID 10001), with all Linux capabilities dropped (`--cap-drop=ALL`), `--security-opt=no-new-privileges:true`, and a read-only root filesystem.
- **Verification:** Container runtime parameter inspection during startup verification tests.

### NFR-003: Host Credential Isolation
- **Priority:** P0
- **Category:** Secret Management
- **Description:** Host environment variables, database credentials, Redis connection strings, and worker access tokens MUST be filtered before spawning sandbox processes. Zero host secrets shall be mounted into containers.
- **Verification:** Container environment audit test checking that `env` output within containers contains zero host environment strings.

### NFR-004: Strict Log Sanitization
- **Priority:** P0
- **Category:** Information Disclosure
- **Description:** The system SHALL filter all console outputs, API responses, and database logs with regex patterns to redact API keys, bearer tokens, private keys, and passwords.
- **Verification:** Automated log sanitizer test scanning synthetic outputs containing dummy API keys.

---

## 3. Reliability & Recoverability

### NFR-005: Worker Crash Isolation
- **Priority:** P0
- **Category:** Fault Tolerance
- **Description:** An unhandled exception or container crash in one evaluation job MUST NOT crash the worker process or terminate concurrent evaluations running on the same host.
- **Verification:** Integration test triggering memory exhaust (OOM) in a sandbox container while verifying worker survival.

### NFR-006: Stale Worker & Orphan Process Recovery
- **Priority:** P0
- **Category:** Recoverability
- **Description:** If a worker host terminates abruptly, the supervisor daemon SHALL detect missing Redis heartbeats within 60 seconds, mark abandoned jobs as `FAILED` with `WORKER_ORPHANED_TIMEOUT`, and sweep orphaned containers on reboot.
- **Verification:** Kill -9 worker simulation test validating database state transition to `FAILED`.

### NFR-007: Database Connection Pool Resilience
- **Priority:** P1
- **Category:** Resilience
- **Description:** The PostgreSQL connection pool (SQLAlchemy + asyncpg) SHALL support automatic reconnection, health pings before checkout, and bounded pool sizing (default: 20 active connections, 10 overflow) to avoid database starvation.
- **Verification:** PostgreSQL restart simulation during idle and active read operations.

### NFR-008: Redis Queue At-Least-Once Delivery
- **Priority:** P1
- **Category:** Reliability
- **Description:** Redis task streams SHALL guarantee at-least-once job delivery through consumer group acknowledgments (`XACK`). Jobs not acknowledged within a configured lock timeout SHALL be re-queued to the dead-letter stream.
- **Verification:** Consumer drop test verifying pending entries list (PEL) re-claiming.

---

## 4. Determinism & Reproducibility

### NFR-009: Mathematical Scoring Determinism
- **Priority:** P0
- **Category:** Reproducibility
- **Description:** Given an identical set of evidence items and scoring ruleset version, the scoring engine MUST produce the exact same composite score and dimension scores every time, with zero deviation ($\Delta = 0.000$).
- **Verification:** Unit test running the scoring calculation 10,000 times on static evidence fixtures, asserting zero variance.

### NFR-010: Snapshot Immutability Guarantee
- **Priority:** P0
- **Category:** Data Integrity
- **Description:** A repository snapshot directory must yield an identical SHA-256 tree checksum regardless of when or where it is cloned from the specified Git commit SHA.
- **Verification:** Snapshot integrity check comparing independent checkouts of the same commit.

### NFR-011: Strict Scoring Ruleset Versioning
- **Priority:** P0
- **Category:** Auditability
- **Description:** Every calculated scorecard MUST record the exact semver version of the scoring ruleset (e.g., `scoring_version: "1.0.0"`). Any modification to weights or formulas requires bumping the version identifier.
- **Verification:** Regression test confirming that historic scorecards retain their original version tag.

---

## 5. Performance & Scalability

### NFR-012: REST API Response Latency
- **Priority:** P1
- **Category:** Performance
- **Description:** Under nominal load (< 50 concurrent requests), standard read endpoints (`GET /repositories/{id}`, `GET /evaluations/{id}/status`, `GET /evaluations/{id}/score`) SHALL respond with p95 latency:
  > `TBD — benchmark required` (Initial target: < 100ms)
- **Measurement Method:** Locust/k6 HTTP load test against mock database records during Phase 16.

### NFR-013: Asynchronous Job Enqueueing Latency
- **Priority:** P1
- **Category:** Performance
- **Description:** `POST /evaluations` SHALL validate the request and enqueue the task to Redis within:
  > `TBD — benchmark required` (Initial target: < 50ms)
- **Measurement Method:** Integration test benchmarking submission endpoint response duration.

### NFR-014: Worker Horizontal Scalability
- **Priority:** P1
- **Category:** Scalability
- **Description:** Worker daemons SHALL be completely stateless, allowing horizontal scaling by adding worker instances connected to the shared Redis queue and PostgreSQL database without code modifications.
- **Verification:** Multi-worker deployment test verifying distributed job processing across 3 worker processes.

### NFR-015: Sandbox Startup Overhead
- **Priority:** P1
- **Category:** Performance
- **Description:** Ephemeral Docker container initialization and capability stripping overhead before executing commands SHALL take no more than:
  > `TBD — benchmark required` (Initial target: < 3.0 seconds on warm host)
- **Measurement Method:** Docker run latency benchmark measuring time from API invocation to container ready state.

### NFR-016: Global Evaluation Duration Bounding
- **Priority:** P0
- **Category:** Bounded Execution
- **Description:** The system SHALL enforce an absolute upper bound of 600 seconds (configurable up to 1800s) on complete evaluation lifecycles, terminating runaway workloads deterministically.
- **Verification:** Test repository executing an infinite sleep loop terminated at timeout boundary.

---

## 6. Observability & Auditability

### NFR-017: Distributed Correlation ID Propagation
- **Priority:** P0
- **Category:** Tracing
- **Description:** Every evaluation request SHALL carry a unique `correlation_id` (UUIDv7) passed in the `X-Correlation-ID` header, propagated across all API logs, Redis messages, worker execution threads, and database records.
- **Verification:** Log trace inspection verifying identical `correlation_id` from HTTP submission to final scorecard persistence.

### NFR-018: Structured JSON Logging
- **Priority:** P1
- **Category:** Observability
- **Description:** All application logs across API, orchestrator, and workers SHALL output structured JSON containing: `timestamp`, `level`, `correlation_id`, `evaluation_id`, `module`, `message`, and `context`.
- **Verification:** Automated log format validation asserting valid JSON lines parsing.

### NFR-019: Prometheus Metric Instrumentation
- **Priority:** P1
- **Category:** Metrics
- **Description:** The system SHALL expose standard Prometheus metrics on `/metrics`, including:
  - `reposcore_evaluations_total` (counter by state)
  - `reposcore_evaluation_duration_seconds` (histogram by stage)
  - `reposcore_active_sandboxes` (gauge)
  - `reposcore_queue_depth` (gauge)
- **Verification:** HTTP scrape verification of `/metrics` endpoint.

---

## 7. Maintainability & Extensibility

### NFR-020: Adapter Architecture for Static Analyzers
- **Priority:** P0
- **Category:** Extensibility
- **Description:** All static analyzers MUST implement the typed `IAnalyzer` Python protocol. Introducing a new analyzer SHALL require zero changes to the orchestration or scoring core.
- **Verification:** Unit test instantiating mock analyzer adhering to `IAnalyzer`.

### NFR-021: Pluggable AI Provider Interface
- **Priority:** P0
- **Category:** Extensibility
- **Description:** The AI engine MUST communicate strictly through the `IAIProvider` protocol, enabling seamless hot-swapping between `LocalProvider` (Ollama) and `ExternalProvider` (OpenAI/Anthropic/Gemini).
- **Verification:** Unit test switching provider implementation via configuration without code alterations.

### NFR-022: Type Safety & Static Linting Compliance
- **Priority:** P1
- **Category:** Code Quality
- **Description:** 100% of backend Python code SHALL pass `mypy --strict` with zero type errors and comply with `ruff` linting rules with zero warnings.
- **Verification:** Automated CI pipeline gate enforcing `mypy` and `ruff check`.

---

## 8. Data Integrity & Retention

### NFR-023: Relational Integrity & Cascade Invariants
- **Priority:** P0
- **Category:** Data Consistency
- **Description:** Database relationships MUST enforce foreign key constraints with explicit delete behaviors (`ON DELETE RESTRICT` for evidence and scores; `ON DELETE CASCADE` for ephemeral tokens).
- **Verification:** Database DDL audit asserting complete foreign key definitions.

### NFR-024: Terminal State Immutability
- **Priority:** P0
- **Category:** Audit Trail
- **Description:** Evaluations in terminal states (`COMPLETED`, `PARTIALLY_COMPLETED`, `FAILED`, `CANCELLED`, `UNSUPPORTED`) MUST be protected against write mutations. Any modification attempt SHALL raise an application error.
- **Verification:** ORM test verifying that updates to completed evaluations are blocked.

---

## 9. Portability & Free-First Ecosystem

### NFR-025: Zero Mandatory Paid Cloud Dependencies
- **Priority:** P0
- **Category:** Open Ecosystem
- **Description:** The system MUST be 100% operational on a standard self-hosted Linux or Docker environment without requiring accounts, credit cards, or API keys for proprietary cloud platforms.
- **Verification:** End-to-end deployment run with all external outbound cloud traffic blocked except public GitHub and OSV.

### NFR-026: Containerized Deployment Parity
- **Priority:** P1
- **Category:** Portability
- **Description:** The entire RepoScore infrastructure (PostgreSQL, Redis, API, Worker, Next.js frontend) SHALL be deployable via a single `docker-compose.yml` manifest.
- **Verification:** `docker compose up` smoke test validating successful service bootstrapping.
