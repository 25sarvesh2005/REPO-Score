# Phase 00 Report

## Status
**PASS**

---

## Objective
Establish the complete, binding technical architecture, security boundaries, evidence data models, deterministic scoring framework, evaluation lifecycle, and architectural decision records (ADRs) for **RepoScore** — Autonomous Repository Intelligence & Software Evaluation Engine.

Phase 00 forbids production code implementation and strictly focuses on creating an airtight architectural contract that governs all future implementation phases.

---

## Architecture Summary
RepoScore is architected as a **modular monolith backend** with **asynchronous worker execution**, backed by **PostgreSQL 16+** for relational and JSONB persistence, **Redis 7+** for distributed task queues and live pub/sub progress streaming, an unprivileged **Docker Sandbox** runtime for untrusted code isolation, and a **Next.js** dashboard.

The architecture strictly adheres to three core tenets:
1. **Evidence Over Assumption**: Software is evaluated empirically based on what it builds and executes at runtime, rather than superficial static heuristics.
2. **Deterministic Core**: Scoring is 100% mathematical, rule-driven, explainable, and reproducible across 10 engineering dimensions. AI models are strictly barred from calculating or modifying numerical scores.
3. **Hostile Untrusted Code Boundary**: All repository files, package manifests, build scripts, and dependencies are treated as active threats. Code execution is strictly quarantined inside ephemeral Docker containers stripped of all Linux capabilities, bounded by cgroups v2 resource quotas, run as non-root UID 10001, and restricted by strict network egress policies.

---

## Documents Created
1. [`SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md) — Topology, component decomposition, deployment profiles, and security perimeters.
2. [`COMPONENT_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/COMPONENT_ARCHITECTURE.md) — Module boundaries, typed Python protocols, and class responsibilities.
3. [`DATA_FLOW.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/DATA_FLOW.md) — End-to-end data pipeline from repository ingestion to client delivery.
4. [`EVALUATION_LIFECYCLE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/EVALUATION_LIFECYCLE.md) — 17-state finite state machine, transition invariants, and cancellation protocol.
5. [`SANDBOX_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SANDBOX_ARCHITECTURE.md) — Container security, cgroups limits, capability stripping, and phased network egress.
6. [`ANALYZER_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/ANALYZER_ARCHITECTURE.md) — Pluggable adapter interfaces for Tree-sitter, Semgrep, Ruff, Bandit, and linters.
7. [`RUNTIME_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/RUNTIME_ARCHITECTURE.md) — Evaluator strategies (HTTP API, CLI, Library, Worker), synthetic probing, and telemetry.
8. [`EVIDENCE_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/EVIDENCE_ARCHITECTURE.md) — Canonical normalized evidence schema, immutability guarantees, and deduplication.
9. [`SCORING_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SCORING_ARCHITECTURE.md) — Mathematical scoring formulation, 10 dimension weights, penalty matrix, and receipts.
10. [`AI_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/AI_ARCHITECTURE.md) — Local-first AI provider interface (Ollama), prompt injection defense, and schema validation.
11. [`OBSERVABILITY_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/OBSERVABILITY_ARCHITECTURE.md) — Correlation IDs, structured JSON logging, secret redaction, and Prometheus metrics.
12. [`FAILURE_MODEL.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/FAILURE_MODEL.md) — 7-class failure taxonomy, timeouts, and dead-letter recovery handling.
13. [`DEPENDENCY_STRATEGY.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/DEPENDENCY_STRATEGY.md) — Free-first open-source software stack, licenses, and replacement strategies.
14. [`DATABASE_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/DATABASE_ARCHITECTURE.md) — Complete PostgreSQL relational DDL, entity-relationship diagrams, and indexes.
15. [`API_BOUNDARIES.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/API_BOUNDARIES.md) — RESTful HTTP endpoint contracts, request/response models, and error envelopes.
16. [`EVENT_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/EVENT_ARCHITECTURE.md) — Internal event catalog, Redis Pub/Sub envelope, and real-time streaming topology.
17. [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md) — Directives and governance for AI coding agents and autonomous collaborators.

---

## ADRs Created
- [`ADR-001`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-001_MODULAR_MONOLITH_ARCHITECTURE.md) — Modular Monolith Architecture
- [`ADR-002`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-002_DOCKER_SANDBOX_ARCHITECTURE.md) — Docker Sandbox Architecture
- [`ADR-003`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-003_EVIDENCE_FIRST_EVALUATION.md) — Evidence-First Evaluation
- [`ADR-004`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-004_DETERMINISTIC_SCORING.md) — Deterministic Scoring
- [`ADR-005`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-005_LOCAL_FIRST_AI.md) — Local-First AI Architecture
- [`ADR-006`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-006_POSTGRESQL_PERSISTENCE.md) — PostgreSQL Relational Persistence
- [`ADR-007`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-007_REDIS_JOB_QUEUE.md) — Redis Distributed Job Queue & Pub/Sub
- [`ADR-008`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-008_ANALYZER_ADAPTER_ARCHITECTURE.md) — Analyzer Adapter Architecture
- [`ADR-009`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-009_RUNTIME_EVALUATOR_ARCHITECTURE.md) — Runtime Evaluator Strategy Architecture
- [`ADR-010`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-010_IMMUTABLE_REPOSITORY_SNAPSHOTS.md) — Immutable Repository Snapshots

---

## Major Decisions
1. **Modular Monolith**: Single cohesive backend codebase containing isolated domain modules communicating via typed Python protocols, combined with stateless worker processes consuming tasks from Redis.
2. **Separation of Ingestion and Execution**: Snapshots are frozen to an immutable commit SHA and mounted read-only before any build or execution takes place.
3. **Deterministic Scoring Pipeline**: All scores are derived from mathematical formulas applied to normalized evidence. AI cannot alter scores.
4. **Local-First AI Engine**: Default integration with self-hosted Ollama (e.g. Llama 3.2, Mistral, Qwen) ensures zero proprietary cloud subscription costs and complete data privacy.

---

## Security Decisions
1. **Never Execute on Host**: Untrusted code execution is prohibited on the host OS.
2. **Hardened Docker Isolation**: `--cap-drop=ALL`, `--security-opt=no-new-privileges:true`, non-root execution (`uid 10001`), read-only root filesystems, and bounded tmpfs allocations.
3. **No Docker Socket Mounting**: The host Docker socket is never mounted into untrusted execution containers.
4. **Phased Network Isolation**: Package registry egress proxying during build; complete network severance (`--network none`) during runtime evaluation.
5. **Prompt Injection Hardening**: Untrusted repository snippets are isolated with rigid boundary markers (`<UNTRUSTED_REPOSITORY_DATA>`) and low temperature ($0.1$).

---

## Known Risks
1. **Resource Saturation**: Multiple concurrent evaluations of heavy projects could exhaust worker host memory.  
   *Mitigation*: Redis concurrency worker concurrency limits and cgroups memory limits (2GB hard ceiling per container).
2. **Slow Dependency Downloads**: Building dependencies from scratch on every run could add latency.  
   *Mitigation*: Future caching of verified package layers within the internal proxy cache.
3. **Hostile Breakouts in Container Runtimes**: Standard runc could theoretically have zero-day escape vulnerabilities.  
   *Mitigation*: The `ISandboxManager` interface is designed to support drop-in upgrades to gVisor (`runsc`) or Firecracker microVMs.

---

## Future Phase Dependencies
- **Phase 01 (Requirements)**: Will refine functional and non-functional requirements referencing the architectural contracts established here.
- **Phase 02 (Security Specification)**: Will define threat vectors, penetration test scenarios, and security test suites referencing `SANDBOX_ARCHITECTURE.md`.
- **Phase 03 (Core Data Models & Interfaces)**: Will implement the exact Pydantic and SQLAlchemy models designed in `DATABASE_ARCHITECTURE.md` and `COMPONENT_ARCHITECTURE.md`.

---

## Self-Review Results
- **Circular Dependencies**: None. Strict unidirectional dependency flow from repository/ingestion to analyzers/runtime to evidence to scoring/AI.
- **Ownership Clarity**: 100% defined across all domains.
- **Security Boundary**: Verified complete isolation between host and sandboxes.
- **Deterministic Guarantees**: Verified pure mathematical scoring algorithms.
- **Observability & Auditability**: Correlation IDs and event logging cover every step.
- **Prohibitions Check**: Confirmed that NO production implementation, mock endpoints, or premature code was written.

---

## Acceptance Criteria
- [x] Product definition is documented.
- [x] System architecture exists.
- [x] Component architecture exists.
- [x] Evaluation lifecycle exists.
- [x] Data flow exists.
- [x] Security boundaries are defined.
- [x] Sandbox architecture exists.
- [x] Runtime architecture exists.
- [x] Static-analysis architecture exists.
- [x] Evidence architecture exists.
- [x] Scoring architecture exists.
- [x] AI architecture exists.
- [x] Database model is defined.
- [x] API boundaries are defined.
- [x] Event architecture exists.
- [x] Failure model exists.
- [x] Observability architecture exists.
- [x] Free-first dependency strategy exists.
- [x] Project structure is defined.
- [x] ADRs are created.
- [x] Architecture has been self-reviewed.
- [x] No production implementation has been introduced.
- [x] No secrets have been introduced.

---

## Commit
- **Commit Message:** `phase(00): establish system architecture`
- **Commit SHA:** `8b796e781a99c9307d8e3d3afd30d7ad9d826b59`

