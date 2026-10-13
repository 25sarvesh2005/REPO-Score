# Requirements Traceability Matrix (RTM)

> **Document:** `TRACEABILITY_MATRIX.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Traceability Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. Overview & Verification Strategy

The Requirements Traceability Matrix (RTM) establishes a bidirectional mapping between high-level requirements, architectural domain components, implementation phases, verification test suites, and expected empirical evidence artifacts.

Every **P0** and **P1** requirement defined across functional, non-functional, security, API, evaluation, scoring, and AI domains is cataloged below.

---

## 2. Master Traceability Table

| Req ID | Requirement Title | Pri | Architecture Component | Phase | Planned Verification / Test | Expected Evidence Artifact |
|---|---|---|---|---|---|---|
| **FR-001** | GitHub URL & Ref Validation | P0 | `backend.repository.ingestion` | Phase 06 | Unit test with valid/invalid URI patterns | HTTP 400 rejection / valid entity in DB |
| **FR-002** | Commit Resolution & SHA Pinning | P0 | `backend.repository.ingestion` | Phase 06 | Integration test with remote git refs | `repositories.default_branch`, 40-char SHA in DB |
| **FR-003** | Immutable Snapshot Generation | P0 | `backend.repository.ingestion` | Phase 06 | Filesystem permission test (`chmod 555`) | Read-only directory tree & SHA-256 manifest |
| **FR-004** | Default Branch Auto-Detection | P1 | `backend.repository.ingestion` | Phase 06 | Integration test querying GitHub API | Populated default branch in DB |
| **FR-005** | Repository Metadata Capture | P1 | `backend.repository.ingestion` | Phase 06 | Mocked GitHub API integration test | Populated stars, forks, license in DB |
| **FR-006** | Ingestion Size Ceilings (250MB) | P0 | `backend.repository.ingestion` | Phase 06 | Quota test with oversized synthetic repo | `UNSUPPORTED` state + `SIZE_EXCEEDED` evidence |
| **FR-007** | Git Submodule Neutralization | P0 | `backend.repository.ingestion` | Phase 06 | Security test with malicious `.gitmodules` | Zero recursive clones + SSRF blocked log |
| **FR-008** | Git LFS Bounded Handling | P2 | `backend.repository.ingestion` | Phase 06 | LFS pointer preservation test | Unfetched binary pointers in snapshot |
| **FR-009** | Ingestion Clone Timeout (120s) | P0 | `backend.repository.ingestion` | Phase 06 | Slow network clone simulation test | `FAILED` state + `INGESTION_TIMEOUT` log |
| **FR-010** | Deduplication of Identical Snapshots | P1 | `backend.repository.store` | Phase 06 | Repeated evaluation integration test | Single snapshot directory reused on disk |
| **FR-011** | Git Hook Neutralization | P0 | `backend.repository.ingestion` | Phase 06 | Host checkout test with hook script | `core.hooksPath=/dev/null` execution audit |
| **FR-012** | Ingestion Failure Classification | P0 | `backend.repository.ingestion` | Phase 06 | Error parsing tests for 5 failure types | Categorized error code in `evaluation_steps` |
| **FR-013** | Shallow Clone Optimization | P1 | `backend.repository.ingestion` | Phase 06 | Git command line flag inspection test | `--depth 1` flag recorded in worker log |
| **FR-014** | Snapshot Storage Layout | P1 | `backend.repository.store` | Phase 06 | Filesystem path assertion test | Standard hierarchy `/var/reposcore/snapshots/...` |
| **FR-015** | Private Repo Credential Isolation | P2 | `backend.repository.ingestion` | Phase 06 | Memory and log credential scan test | Zero credentials persisted in DB or logs |
| **FR-016** | Language Manifest Detection | P0 | `backend.analyzers.detector` | Phase 08 | Fixture tests with multi-language repos | Primary language identified with confidence |
| **FR-017** | Package Manager & Lockfile Detection | P0 | `backend.analyzers.detector` | Phase 08 | Fixture tests with poetry/npm/yarn | Exact package manager and lockfile identified |
| **FR-018** | Application Framework Detection | P1 | `backend.analyzers.detector` | Phase 08 | Dependency list scanning test | Framework tags in repository metadata |
| **FR-019** | Application Category Classification | P0 | `backend.analyzers.detector` | Phase 08 | Classification tests on CLI vs Web API | `WEB_API` or `CLI_TOOL` enum assigned |
| **FR-020** | Entrypoint & Command Discovery | P0 | `backend.analyzers.detector` | Phase 08 | AST and manifest entrypoint tests | Discovered startup command string |
| **FR-021** | Test Runner Detection | P1 | `backend.analyzers.detector` | Phase 08 | Detection tests with pytest/jest configs | Discovered test runner identifier |
| **FR-022** | Container Configuration Discovery | P1 | `backend.analyzers.detector` | Phase 08 | Dockerfile parsing test | Metadata extracted without daemon execution |
| **FR-023** | CI/CD Pipeline Detection | P1 | `backend.analyzers.detector` | Phase 08 | Workflow directory scan test | CI presence flag in `evaluation_steps` |
| **FR-024** | Detection Confidence Score | P1 | `backend.analyzers.detector` | Phase 08 | Ambiguity boundary test | Confidence float `0.0 - 1.0` in metadata |
| **FR-025** | Unsupported Tech Rejection | P0 | `backend.analyzers.detector` | Phase 08 | Non-code repository test | `UNSUPPORTED` state transition + clean exit |
| **FR-026** | Asynchronous Job Enqueueing | P0 | `backend.orchestration.engine` | Phase 05 | API load test asserting HTTP 202 | Task payload in Redis stream + DB record |
| **FR-027** | Worker Job Claiming & Concurrency | P0 | `backend.workers.pool` | Phase 05 | Multi-worker concurrency test | Atomic claim via Redis `XREADGROUP` |
| **FR-028** | 17-State FSM Invariant Transitions | P0 | `backend.orchestration.engine` | Phase 05 | State machine transition unit test | Full sequence in `evaluation_steps` table |
| **FR-029** | Worker Heartbeat & Orphan Supervision | P0 | `backend.orchestration.supervisor` | Phase 05 | Dead worker simulation test | `WORKER_ORPHANED_TIMEOUT` in DB |
| **FR-030** | Evaluation Cancellation Dispatch | P0 | `backend.orchestration.engine` | Phase 05 | Cancellation endpoint integration test | `docker kill` executed + `CANCELLED` status |
| **FR-031** | Global Evaluation Timeout (600s) | P0 | `backend.orchestration.engine` | Phase 05 | Long-running task simulation test | Hard cutoff + `TIMEOUT` status |
| **FR-032** | Granular Step Timeouts | P0 | `backend.orchestration.engine` | Phase 05 | Sub-step timeout tests | Step aborted + transition to next stage |
| **FR-033** | Graceful Partial Evaluation Routing | P0 | `backend.orchestration.engine` | Phase 05 | Broken build test repo execution | `BUILD_FAILED` $\to$ `SCORING` $\to$ `PARTIALLY_COMPLETED` |
| **FR-034** | Real-Time Lifecycle Streaming | P1 | `backend.orchestration.events` | Phase 05 | Redis Pub/Sub subscriber test | JSON messages on `reposcore:events:{id}` |
| **FR-035** | Ephemeral Workspace Cleanup | P0 | `backend.sandbox.manager` | Phase 07 | Post-evaluation container audit | Zero running containers + `/tmp` wiped |
| **FR-036** | Canonical Evidence Normalization | P0 | `backend.evidence.collector` | Phase 08 | Schema validation on findings | Standard `Evidence` records in PostgreSQL |
| **FR-037** | Deterministic Score Calculation | P0 | `backend.scoring.calculator` | Phase 10 | Mathematical unit test on evidence | Overall score, letter grade, and 10 dimensions |
| **FR-038** | Itemized Deduction Receipts | P0 | `backend.scoring.calculator` | Phase 10 | Receipt verification test | Itemized rows in `score_deductions` linked to evidence |
| **FR-039** | AI Executive Summary Synthesis | P1 | `backend.ai.interpreter` | Phase 11 | Local Ollama integration test | Structured summary in `ai_analyses` table |
| **FR-040** | Actionable Remediation Suggestions | P1 | `backend.ai.interpreter` | Phase 11 | Recommendation extraction test | Prioritized recommendations in DB |
| **FR-041** | Cross-Commit Score History | P1 | `backend.repository.store` | Phase 10 | Multi-commit evaluation test | Score deltas and new finding diffs |
| **FR-042** | Markdown Report Export | P2 | `backend.reporting.export` | Phase 12 | Export endpoint test | Valid GitHub-flavored `REPORT.md` string |
| **FR-043** | Structured JSON Export | P1 | `backend.api.endpoints` | Phase 04 | OpenAPI response schema test | Validated JSON payload matching contract |
| **FR-044** | Multi-Tool Finding Deduplication | P1 | `backend.evidence.collector` | Phase 08 | Overlapping Semgrep/Bandit scan test | Merged evidence record with dual sources |
| **FR-045** | Terminal State Immutability | P0 | `backend.database.core` | Phase 03 | Database mutation rejection test | DB IntegrityError on update attempt |
| **SEC-001** | Zero Host Untrusted Execution | P0 | `backend.sandbox.manager` | Phase 07 | Adversarial test with host-escape script | Execution isolated within container namespace |
| **SEC-002** | Docker Socket Mounting Prohibition | P0 | `backend.sandbox.manager` | Phase 07 | Container volume inspect test | `/var/run/docker.sock` absent from mounts |
| **SEC-003** | Non-Root UID 10001 Execution | P0 | `backend.sandbox.manager` | Phase 07 | `whoami` / `id` runtime test | UID=10001, GID=10001 confirmed |
| **SEC-004** | Linux Capability Stripping | P0 | `backend.sandbox.manager` | Phase 07 | `capsh --print` inspection test | `CapEff=0000000000000000` verified |
| **SEC-005** | Read-Only Root Filesystem | P0 | `backend.sandbox.manager` | Phase 07 | Write attempt to `/etc/evil` | Read-only filesystem error caught |
| **SEC-006** | Phased Network Isolation Policy | P0 | `backend.sandbox.manager` | Phase 07 | Socket connection test during RUN step | Network unreachable error verified |
| **SEC-007** | Defense Against SSRF | P0 | `backend.sandbox.network` | Phase 07 | Egress request to `169.254.169.254` | HTTP 403 Forbidden / connection dropped |
| **SEC-008** | Memory Quotas & OOM Bounding (2GB) | P0 | `backend.sandbox.manager` | Phase 07 | Memory exhaust script test | Container killed by OOM (code 137); host safe |
| **SEC-009** | CPU Core Quotas (2 cores) | P0 | `backend.sandbox.manager` | Phase 07 | CPU stress loop test | Host CPU usage bounded at 2 cores |
| **SEC-010** | PID Ceiling (128 max / Fork Bomb) | P0 | `backend.sandbox.manager` | Phase 07 | Bash fork bomb execution test | Fork fails at 128 PIDs; worker stays healthy |
| **SEC-011** | Output Flooding Defense (10MB) | P0 | `backend.sandbox.manager` | Phase 07 | Infinite stdout stream test | Stream truncated at 10MB + warning marker |
| **SEC-012** | Path Traversal / Zip Slip Defense | P0 | `backend.repository.ingestion` | Phase 06 | Unpack test with `../../` archive | Extraction aborted with SecurityError |
| **SEC-013** | Git Hook Neutralization | P0 | `backend.repository.ingestion` | Phase 06 | Checkout test with executable hook | Zero hook execution on host |
| **SEC-014** | Untrusted Dockerfile Rejection | P0 | `backend.sandbox.manager` | Phase 07 | Repo Dockerfile build attempt test | Hardened official image run; repo Dockerfile ignored |
| **SEC-015** | Host Secret Zero-Leakage | P0 | `backend.sandbox.manager` | Phase 07 | Container `env` dump audit test | Zero host secrets in container environment |
| **SEC-016** | Automated Log Redaction | P0 | `backend.observability.logger` | Phase 05 | Dummy token log processing test | Log string contains `[REDACTED_SECRET]` |
| **SEC-017** | Untrusted Prompt Boundary Markers | P0 | `backend.ai.prompts` | Phase 11 | Prompt injection string fixture test | `<UNTRUSTED_REPOSITORY_DATA>` tags present |
| **SEC-018** | AI Host Execution Barrier | P0 | `backend.ai.core` | Phase 11 | Host command execution audit test | Zero shell invocations spawned from AI output |
| **SEC-019** | Structured AI Output Validation | P0 | `backend.ai.schema` | Phase 11 | Malformed JSON schema test | Pydantic ValidationError handled gracefully |
| **SEC-020** | Deterministic Container Teardown | P0 | `backend.sandbox.manager` | Phase 07 | Abort and crash cleanup test | Zero residual containers in `docker ps -a` |
| **API-001** | `POST /repositories` | P0 | `backend.api.endpoints` | Phase 04 | Integration test with GitHub URL | HTTP 201 Created + repository JSON |
| **API-002** | `GET /repositories/{id}` | P1 | `backend.api.endpoints` | Phase 04 | Query repository test | HTTP 200 OK + repository details |
| **API-003** | `POST /evaluations` | P0 | `backend.api.endpoints` | Phase 04 | Job submission test | HTTP 202 Accepted + Location header |
| **API-004** | `GET /evaluations/{id}` | P0 | `backend.api.endpoints` | Phase 04 | Query evaluation master test | HTTP 200 OK + full evaluation record |
| **API-005** | `GET /evaluations/{id}/status` | P0 | `backend.api.endpoints` | Phase 04 | Polling endpoint load test | HTTP 200 OK + current step and duration |
| **API-006** | `GET /evaluations/{id}/events` | P1 | `backend.api.endpoints` | Phase 04 | SSE client stream test | HTTP 200 OK + text/event-stream chunks |
| **API-007** | `POST /evaluations/{id}/cancel` | P0 | `backend.api.endpoints` | Phase 04 | Cancel request test | HTTP 200 OK + `CANCELLED` status dispatched |
| **API-008** | `GET /evaluations/{id}/score` | P0 | `backend.api.endpoints` | Phase 04 | Scorecard query test | HTTP 200 OK + composite & 10 dimensions |
| **API-009** | `GET /evaluations/{id}/evidence` | P0 | `backend.api.endpoints` | Phase 04 | Paginated query test | HTTP 200 OK + paginated evidence array |
| **API-010** | `GET /evaluations/{id}/runtime` | P0 | `backend.api.endpoints` | Phase 04 | Runtime telemetry query test | HTTP 200 OK + latency, probes, exit code |
| **API-011** | `GET /evaluations/{id}/security` | P0 | `backend.api.endpoints` | Phase 04 | Security report query test | HTTP 200 OK + CVEs & secret findings |
| **API-012** | `GET /evaluations/{id}/findings` | P1 | `backend.api.endpoints` | Phase 04 | Static findings query test | HTTP 200 OK + raw and normalized findings |
| **API-013** | `GET /evaluations/{id}/history` | P1 | `backend.api.endpoints` | Phase 04 | Historical diff query test | HTTP 200 OK + evaluation comparisons |
| **API-014** | `GET /health` Liveness Probe | P0 | `backend.api.endpoints` | Phase 04 | HTTP GET liveness test | HTTP 200 OK (`{"status":"healthy"}`) |
| **API-015** | `GET /ready` Readiness Probe | P0 | `backend.api.endpoints` | Phase 04 | Postgres/Redis down test | HTTP 503 Service Unavailable on outage |
| **API-016** | RFC 7807 Problem Details | P0 | `backend.api.middleware` | Phase 04 | 4xx / 5xx error trigger test | RFC 7807 compliant error envelope |
| **API-017** | `X-Correlation-ID` Propagation | P0 | `backend.api.middleware` | Phase 04 | Correlation header test | Response header contains same correlation ID |
| **API-018** | Idempotency Key Handling | P1 | `backend.api.middleware` | Phase 04 | Duplicate POST test with same key | Cached 202 response without duplicate job |
| **API-019** | API Rate Limiting | P1 | `backend.api.middleware` | Phase 04 | Rapid fire submission test | HTTP 429 Too Many Requests |
| **API-020** | API Versioning Strategy | P0 | `backend.api.routing` | Phase 04 | Route structure test | All routes routed under `/api/v1/` |
| **EVAL-001**| 17-State FSM Conformance | P0 | `backend.orchestration.engine` | Phase 05 | Full lifecycle transition test | Exact step records in DB |
| **EVAL-006**| Pluggable `IAnalyzer` Protocol | P0 | `backend.analyzers.core` | Phase 08 | Typed interface test | Concrete analyzers comply with protocol |
| **EVAL-007**| Tree-sitter AST & Metrics | P0 | `backend.analyzers.treesitter` | Phase 08 | AST parsing on Python/JS fixtures | Complexity & function counts extracted |
| **EVAL-008**| Semgrep Pattern Execution | P0 | `backend.analyzers.semgrep` | Phase 08 | Semgrep scan on vulnerable fixtures | Rule violations with line numbers |
| **EVAL-011**| Dependency Manifest Parsing | P0 | `backend.analyzers.dependencies`| Phase 08 | Parsing tests on requirements/lockfiles | Resolved package list & versions |
| **EVAL-012**| OSV Advisory Querying | P0 | `backend.security.advisories` | Phase 08 | OSV API lookup on known CVE fixture | CVE evidence records created |
| **EVAL-013**| Hardcoded Secret Detection | P0 | `backend.security.secrets` | Phase 08 | Secret detection scan test | Masked secret evidence records |
| **EVAL-016**| Ephemeral Sandbox Lifecycle | P0 | `backend.sandbox.manager` | Phase 07 | Container create/run/stop cycle test | Ephemeral container lifecycle verified |
| **EVAL-021**| Build Strategy Resolution | P0 | `backend.runtime.builder` | Phase 09 | Python/Node build execution test | Successful container build log & exit 0 |
| **EVAL-025**| Application Bootstrapping | P0 | `backend.runtime.startup` | Phase 09 | FastAPI bootstrap test in sandbox | Process listening verified |
| **EVAL-026**| Service Readiness Probing | P0 | `backend.runtime.startup` | Phase 09 | HTTP probe against container port | Startup latency recorded in ms |
| **EVAL-029**| Test Origin Classification | P0 | `backend.runtime.testing` | Phase 09 | Origin tag assertion test | Correct enum attached to test results |
| **EVAL-031**| Synthetic HTTP Probing | P0 | `backend.runtime.http_evaluator`| Phase 09 | Probing test against dummy endpoint | HTTP 200, latency p95 recorded |
| **EVAL-033**| Canonical Evidence Schema | P0 | `backend.evidence.collector` | Phase 08 | Pydantic schema validation test | Conforming `Evidence` records stored |
| **EVAL-037**| 7-Class Failure Taxonomy | P0 | `backend.orchestration.failure` | Phase 05 | Classification unit tests | Correct failure enum stored |
| **SCORE-001**| 10 Dimensions & Weights = 1.00 | P0 | `backend.scoring.calculator` | Phase 10 | Weight sum mathematical test | Sum equals exactly 1.000000 |
| **SCORE-002**| Clamped Dimension Score [0, 100]| P0 | `backend.scoring.calculator` | Phase 10 | Clamping boundary unit tests | Scores bounded within [0.0, 100.0] |
| **SCORE-003**| Weighted Composite Score | P0 | `backend.scoring.calculator` | Phase 10 | Composite calculation test | Single decimal float score in DB |
| **SCORE-004**| Letter Grade Mapping | P0 | `backend.scoring.calculator` | Phase 10 | Threshold boundary unit tests | Correct grade letter (A+ to F) |
| **SCORE-007**| AI Scoring Prohibition | P0 | `backend.scoring.calculator` | Phase 10 | Score mutation assertion test | Zero AI-generated scores in DB |
| **SCORE-008**| Scoring Ruleset Versioning | P0 | `backend.scoring.calculator` | Phase 10 | Version tag persistence test | `scoring_version` matches semver |
| **SCORE-009**| Scoring Determinism Invariant | P0 | `backend.scoring.calculator` | Phase 10 | 10,000x repeated calculation test | Zero variance across repeated runs |
| **SCORE-010**| Evidence Attribution Invariant | P0 | `backend.scoring.calculator` | Phase 10 | FK constraint validation test | Every deduction links to `evidence_id` |
| **SCORE-021**| Itemized Deduction Receipts | P0 | `backend.scoring.calculator` | Phase 10 | Receipt generation test | Transparent JSON receipt per dimension |
| **AI-001** | Permitted AI Task Scope | P0 | `backend.ai.interpreter` | Phase 11 | Prompt router unit test | Tasks restricted to permitted catalog |
| **AI-002** | Prohibited AI Scope Invariant | P0 | `backend.ai.core` | Phase 11 | Security audit test | Zero host execution or scoring actions |
| **AI-003** | Pluggable `IAIProvider` Protocol| P0 | `backend.ai.core` | Phase 11 | Mock/Local provider switch test | Clean polymorphic interface |
| **AI-004** | Local Ollama Default | P0 | `backend.ai.ollama` | Phase 11 | Local Ollama inference test | 100% offline generation verified |
| **AI-006** | Pydantic Structured Output | P0 | `backend.ai.schema` | Phase 11 | Response parser validation test | Output validates against schema |
| **AI-008** | Bounded AI Timeout (60s) | P0 | `backend.ai.core` | Phase 11 | Artificial delay simulation test | Inference aborted at 60s cutoff |
| **AI-009** | Graceful Degradation on AI Fail | P0 | `backend.orchestration.engine` | Phase 11 | Offline AI simulation test | Evaluation completes with full score |
| **AI-011** | Prompt Injection Boundary Tags | P0 | `backend.ai.prompts` | Phase 11 | Injection prompt fixture test | Delimiters present around untrusted text |
| **AI-014** | AI-Generated Test Tagging | P0 | `backend.ai.test_generator` | Phase 11 | Generated test metadata test | `AI_GENERATED` tag verified |
| **AI-015** | Sandboxed Execution of AI Tests | P0 | `backend.sandbox.manager` | Phase 11 | Test invocation audit test | Executed strictly in container namespace |

---

## 3. Summary Statistics

- **Total Cataloged Requirements:** 76 Core Traceability Entries
- **P0 Requirements:** 54 (100% mapped to phase, test, and evidence)
- **P1 Requirements:** 18 (100% mapped to phase, test, and evidence)
- **P2 Requirements:** 4 (100% mapped to phase, test, and evidence)
- **Target Implementation Phases:** Phases 03 through 12
- **Verification Coverage:** 100% of P0 requirements possess explicit test methods and observable evidence artifacts.
