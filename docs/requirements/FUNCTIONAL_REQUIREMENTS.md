# Functional Requirements Specification

> **Document:** `FUNCTIONAL_REQUIREMENTS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Requirements Baseline  
> **Phase:** Phase 01 — Requirements Engineering  
> **Authority:** `phases/01_REQUIREMENTS.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Domain Overview

The functional requirements define what RepoScore must do across its primary processing stages:
1. **Repository Ingestion & Snapshotting** (`FR-001` to `FR-015`)
2. **Technology Detection & Classification** (`FR-016` to `FR-025`)
3. **Evaluation Orchestration & Job Lifecycle** (`FR-026` to `FR-035`)
4. **Result Assembly, Scorecards & Reporting** (`FR-036` to `FR-045`)

---

## 2. Repository Ingestion & Snapshotting

### FR-001: URL & Reference Validation
- **Title:** GitHub Repository Reference Validation
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL accept and validate public GitHub repository references formatted as standard HTTPS URLs (e.g., `https://github.com/org/repo`) or shorthand references (`org/repo`). Non-GitHub URLs or malformed URIs MUST be rejected with a 400 Bad Request error.
- **Acceptance Criteria:**
  ```gherkin
  Given a user submits a repository reference string
  When the reference does not conform to the regex "^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$" or "org/repo"
  Then the system must reject the request immediately with HTTP 400
  And must return a structured RFC 7807 error detail stating invalid repository format
  ```

### FR-002: Commit Resolution & Pinned SHA Extraction
- **Title:** Target Commit Resolution
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** When a repository evaluation is triggered with a branch name, tag, or HEAD reference, the system SHALL resolve the reference to an unambiguous, full 40-character hexadecimal Git commit SHA before initiating evaluation.
- **Acceptance Criteria:**
  ```gherkin
  Given a user requests an evaluation for branch "main"
  When the ingestion worker queries the upstream remote repository
  Then the system must resolve and record the exact 40-character commit SHA (e.g. "a1b2c3d4...")
  And all subsequent evaluation steps must bind exclusively to this resolved SHA
  ```

### FR-003: Immutable Snapshot Generation
- **Title:** Tamper-Proof Repository Snapshot Creation
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL create an immutable, read-only directory snapshot of the repository files pinned to the resolved commit SHA on isolated local worker storage (`/var/reposcore/snapshots/{snapshot_id}`). The snapshot must be flagged read-only and checksummed (SHA-256).
- **Acceptance Criteria:**
  ```gherkin
  Given a repository has been cloned at commit SHA "abcdef123..."
  When the worker completes directory extraction to the snapshot storage
  Then the directory permissions must be set to read-only (chmod -R 555)
  And a SHA-256 manifest of all files must be computed and stored in the database
  And upstream repository modifications made during evaluation must not affect the snapshot
  ```

### FR-004: Default Branch Auto-Detection
- **Title:** Remote Default Branch Detection
- **Priority:** P1
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** If no branch or commit reference is explicitly provided by the user, the system SHALL automatically detect and evaluate the repository's remote default branch (typically `main` or `master`).

### FR-005: Repository Metadata Capture
- **Title:** Metadata Harvesting
- **Priority:** P1
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL query the GitHub API to extract repository metadata including: star count, fork count, open issue count, license identifier, creation timestamp, latest commit timestamp, and primary language, storing them in the `repositories` entity.

### FR-006: Ingestion Size Ceilings & Enforced Limits
- **Title:** Maximum Repository Size Protection
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL enforce an uncompressed size ceiling of 250MB (default, configurable) and a maximum file count limit of 25,000 files during ingestion. Repositories exceeding these thresholds MUST be aborted cleanly with state `UNSUPPORTED`.
- **Acceptance Criteria:**
  ```gherkin
  Given an ingested repository uncompresses to greater than 250MB
  When the disk quota monitor detects the size overflow
  Then the ingestion process must terminate immediately
  And the evaluation status must be set to "UNSUPPORTED"
  And the failure reason must record "REPOSITORY_SIZE_EXCEEDS_LIMIT"
  ```

### FR-007: Git Submodule Handling Policy
- **Title:** Submodule Neutralization
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL NOT recursively clone external Git submodules by default. If submodule cloning is explicitly enabled via evaluation options, submodule URLs MUST be validated to prevent loopback attacks, SSRF, or local file access.
- **Acceptance Criteria:**
  ```gherkin
  Given a repository contains a .gitmodules file pointing to "file:///etc/passwd" or "http://169.254.169.254"
  When RepoScore clones the repository
  Then recursive submodule cloning must be disabled
  And any malicious submodule URL must not be fetched
  ```

### FR-008: Git LFS (Large File Storage) Policy
- **Title:** Bounded Git LFS Handling
- **Priority:** P2
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** By default, Git LFS pointer files SHALL be preserved as text pointers without fetching binary payloads. If LFS fetching is enabled, an aggregate payload cap of 50MB SHALL be enforced.

### FR-009: Ingestion Network Timeout
- **Title:** Bounded Clone Execution
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL enforce a hard timeout of 120 seconds on all Git clone and fetch operations. If cloning exceeds 120 seconds, the operation MUST be aborted and marked `FAILED` with `INGESTION_TIMEOUT`.
- **Acceptance Criteria:**
  ```gherkin
  Given a slow or hanging upstream Git server
  When a clone operation takes longer than 120 seconds
  Then the worker process must terminate the git process with SIGKILL
  And the evaluation must transition to status "FAILED"
  And an error event "evaluation.failed" must be published
  ```

### FR-010: Deduplication of Identical Snapshots
- **Title:** Snapshot Deduplication
- **Priority:** P1
- **Owner Component:** Repository Store (`backend.repository.store`)
- **Description:** If an immutable snapshot for a given repository and exact commit SHA already exists on disk and is verified by checksum, the system SHALL reuse the existing snapshot rather than re-cloning from GitHub.

### FR-011: Git Hook Neutralization
- **Title:** Defense Against Malicious Git Hooks
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL clone repositories using `--config core.hooksPath=/dev/null` and delete any `.git/hooks` directories immediately upon archive creation to ensure no client-side hooks execute on the host during checkout.
- **Acceptance Criteria:**
  ```gherkin
  Given a repository containing an executable ".git/hooks/post-checkout" script
  When RepoScore checks out the repository snapshot on the host
  Then core.hooksPath must point to "/dev/null"
  And the hook script must never be executed on the host
  ```

### FR-012: Ingestion Failure Classification
- **Title:** Diagnostic Ingestion Error Capture
- **Priority:** P0
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** When ingestion fails, the system SHALL categorize the failure into: `REPOSITORY_NOT_FOUND`, `AUTH_REQUIRED`, `RATE_LIMITED`, `SIZE_EXCEEDED`, `CORRUPT_GIT_OBJECTS`, or `TIMEOUT`, storing full diagnostic details in `evaluation_steps`.

### FR-013: Shallow Clone Optimization
- **Title:** Depth-1 Shallow Clones
- **Priority:** P1
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** The system SHALL perform shallow clones with depth 1 (`git clone --depth 1`) whenever evaluating a specific branch or commit, minimizing bandwidth and disk consumption.

### FR-014: Archive Storage Layout
- **Title:** Standardized Snapshot Storage Hierarchy
- **Priority:** P1
- **Owner Component:** Storage Manager (`backend.repository.store`)
- **Description:** Snapshots SHALL be persisted under a hierarchical directory layout: `/var/reposcore/snapshots/{repo_id}/{commit_sha}/`, protected by POSIX filesystem permissions restricting access strictly to the `reposcore` worker daemon.

### FR-015: Authentication Boundary for Private Repositories
- **Title:** Private Repository Credential Isolation
- **Priority:** P2
- **Owner Component:** Ingestion Subsystem (`backend.repository.ingestion`)
- **Description:** When private repository authentication is configured, GitHub Personal Access Tokens (PAT) or GitHub App installation tokens SHALL be supplied via encrypted transient headers and NEVER logged, persisted in database fields, or exposed in snapshot files.

---

## 3. Technology Detection & Repository Classification

### FR-016: Multi-Language Manifest Detection
- **Title:** Deterministic Language Identification
- **Priority:** P0
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL inspect manifest files to identify programming languages:
  - Python: `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`, `Pipfile`
  - Node.js / TypeScript: `package.json`, `tsconfig.json`
  - Java: `pom.xml`, `build.gradle`
  - Go: `go.mod`
  - Rust: `Cargo.toml`
- **Acceptance Criteria:**
  ```gherkin
  Given a repository containing "pyproject.toml" and "requirements.txt"
  When the detector processes the repository manifest files
  Then the primary language must be identified as "Python" with confidence 1.0
  ```

### FR-017: Package Manager & Lockfile Detection
- **Title:** Package Manager Resolution
- **Priority:** P0
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL detect the specific package manager and lockfile:
  - Python: `poetry.lock`, `Pipfile.lock`, `pdm.lock`, `requirements.txt`
  - Node.js: `package-lock.json` (npm), `yarn.lock` (yarn), `pnpm-lock.yaml` (pnpm), `bun.lockb` (bun)
  - Java: Maven (`pom.xml`), Gradle (`build.gradle`)

### FR-018: Framework Identification
- **Title:** Application Framework Detection
- **Priority:** P1
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL detect high-level frameworks by scanning dependency lists in manifests (e.g., FastAPI, Flask, Django, Express, NestJS, Next.js, Spring Boot).

### FR-019: Application Category Classification
- **Title:** Repository Type Classification
- **Priority:** P0
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL classify each repository into one of the following operational categories:
  1. `WEB_API` (exposes HTTP REST or GraphQL server)
  2. `CLI_TOOL` (command-line utility or terminal application)
  3. `LIBRARY` (reusable package without standalone daemon entrypoint)
  4. `BACKGROUND_WORKER` (event consumer or queue listener)
  5. `UNSUPPORTED` (unrecognized technology or non-code repository)
- **Acceptance Criteria:**
  ```gherkin
  Given a repository contains "uvicorn.run" and FastAPI in dependencies
  When the classification rules are evaluated
  Then the repository must be classified as "WEB_API"
  And the runtime evaluator selected must be "HttpApiEvaluator"
  ```

### FR-020: Entrypoint & Startup Command Identification
- **Title:** Automatic Entrypoint Discovery
- **Priority:** P0
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL heuristically resolve the primary entrypoint:
  - Python: `main.py`, `app.py`, `run.py`, `cli.py`, or `[project.scripts]` in `pyproject.toml`
  - Node.js: `"main"`, `"bin"`, or `"scripts.start"` in `package.json`

### FR-021: Test Framework Detection
- **Title:** Test Runner Discovery
- **Priority:** P1
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL identify test runners and configurations: `pytest`, `unittest`, `jest`, `mocha`, `vitest`, `cargo test`, `go test`.

### FR-022: Container Configuration Discovery
- **Title:** Dockerfile & Compose Manifest Detection
- **Priority:** P1
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL detect repository-provided `Dockerfile`, `docker-compose.yml`, or `.devcontainer/devcontainer.json` files for structural metadata extraction. Repository Dockerfiles MUST NOT be executed directly by the host Docker daemon.

### FR-023: CI/CD Pipeline Detection
- **Title:** CI/CD Workflow Audit
- **Priority:** P1
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** The system SHALL detect the existence of `.github/workflows/*.yml`, `.gitlab-ci.yml`, or `Jenkinsfile` and evaluate them as signals for the **Engineering Maturity** scoring dimension.

### FR-024: Detection Confidence Representation
- **Title:** Confidence Scoring for Inferred Metadata
- **Priority:** P1
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** For each detected technology, framework, and category, the system SHALL output a confidence value between `0.0` and `1.0`. Ambiguous repositories (confidence < 0.6) SHALL be flagged for conservative execution.

### FR-025: Unsupported Technology Rejection
- **Title:** Graceful Handling of Unsupported Stacks
- **Priority:** P0
- **Owner Component:** Detection Engine (`backend.analyzers.detector`)
- **Description:** If a repository contains no detectable supported language or manifests, the system SHALL transition the evaluation to `UNSUPPORTED`, generate explanatory diagnostics, and cleanly complete the job.

---

## 4. Evaluation Orchestration & Job Lifecycle

### FR-026: Asynchronous Evaluation Enqueueing
- **Title:** Job Enqueueing
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** When an evaluation is requested, the system SHALL create an `evaluations` record in status `QUEUED`, generate a unique UUIDv7, assign a distributed `correlation_id`, and push a task to the Redis stream `reposcore:evaluations:queued`.
- **Acceptance Criteria:**
  ```gherkin
  Given a valid repository snapshot
  When POST /evaluations is called
  Then an evaluation record must be persisted in PostgreSQL with status "QUEUED"
  And a job payload must be published to Redis queue within 50ms
  And the HTTP response status must be 202 Accepted
  ```

### FR-027: Worker Job Claiming & Concurrency Limits
- **Title:** Atomic Job Acquisition
- **Priority:** P0
- **Owner Component:** Worker Pool (`backend.workers.pool`)
- **Description:** Workers SHALL acquire evaluation jobs using atomic Redis consumer group locks (`XREADGROUP`). Each worker instance SHALL process at most 1 concurrent evaluation per 2 CPU cores to prevent host resource starvation.

### FR-028: Discrete Lifecycle State Machine Transitions
- **Title:** Strict Lifecycle State Transitions
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** The evaluation MUST progress through the defined 17-state finite state machine (FSM). Every state transition SHALL be recorded atomically in `evaluation_steps` with start/end timestamps and step status.
- **Acceptance Criteria:**
  ```gherkin
  Given an evaluation is in state "INGESTING"
  When repository extraction completes successfully
  Then the evaluation must transition to "ANALYZING"
  And an evaluation_step record for "INGESTING" must be updated with status "SUCCESS"
  And an event "evaluation.step.completed" must be emitted to Redis Pub/Sub
  ```

### FR-029: Worker Heartbeats & Orphan Supervision
- **Title:** Heartbeat & Stale Worker Recovery
- **Priority:** P0
- **Owner Component:** Worker Supervisor (`backend.orchestration.supervisor`)
- **Description:** Active workers SHALL emit heartbeats to Redis key `reposcore:worker:heartbeat:{worker_id}` every 5 seconds. If a worker fails to emit a heartbeat for 60 seconds, the supervisor SHALL mark orphaned evaluations as `FAILED` with `WORKER_ORPHANED_TIMEOUT`.
- **Acceptance Criteria:**
  ```gherkin
  Given a worker process dies abruptly during the "TESTING" step
  When 60 seconds elapse without a Redis heartbeat from that worker
  Then the supervisor must mark the active evaluation as "FAILED"
  And any running Docker containers for that evaluation must be terminated
  ```

### FR-030: Evaluation Cancellation Dispatch
- **Title:** Client-Initiated Cancellation
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** When `POST /evaluations/{id}/cancel` is received, the system SHALL set Redis abort key `reposcore:cancel:{id}`. Workers SHALL check this key at all step boundaries and during output streaming, immediately stopping sandbox containers and marking the job `CANCELLED`.
- **Acceptance Criteria:**
  ```gherkin
  Given an evaluation is actively running in state "BUILDING"
  When the cancellation endpoint POST /evaluations/{id}/cancel is invoked
  Then the worker must detect the cancellation signal within 2 seconds
  And must execute "docker kill" on the sandbox container
  And the evaluation status must be updated to "CANCELLED"
  ```

### FR-031: Global Execution Timeout Enforcement
- **Title:** Maximum Evaluation Duration
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** The system SHALL enforce an overall evaluation timeout (default: 600 seconds, configurable up to 1800 seconds). If total runtime exceeds this limit, the evaluation MUST transition to `TIMEOUT`.

### FR-032: Step-Level Timeout Bounding
- **Title:** Granular Step Timeouts
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** Each discrete pipeline step SHALL enforce dedicated timeouts:
  - Ingestion: 120s
  - Static Analysis: 180s
  - Container Build: 300s
  - Startup Probing: 60s
  - Runtime Probing: 120s
  - AI Interpretation: 60s

### FR-033: Graceful Partial Evaluation Routing
- **Title:** Partial Completion on Build/Startup Failure
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** If a repository fails during `BUILDING` or `STARTING`, the orchestrator SHALL NOT trigger a catastrophic `FAILED` state. It SHALL record the failure evidence, transition to `SCORING`, assess appropriate dimension penalties, and finalize in `PARTIALLY_COMPLETED`.
- **Acceptance Criteria:**
  ```gherkin
  Given a repository has a syntax error that prevents building
  When the build step exits with return code 1
  Then the status must transition to "BUILD_FAILED" and then "SCORING"
  And the evaluation must terminate with status "PARTIALLY_COMPLETED"
  And static analysis and security findings must remain accessible to the user
  ```

### FR-034: Real-time Event Publication (Redis Pub/Sub)
- **Title:** Real-Time Lifecycle Streaming
- **Priority:** P1
- **Owner Component:** Event Dispatcher (`backend.orchestration.events`)
- **Description:** The orchestrator SHALL publish all state transitions, progress percentages, and log chunks to Redis channel `reposcore:events:{evaluation_id}` for consumption by the SSE gateway.

### FR-035: Ephemeral Workspace Cleanup
- **Title:** Deterministic Resource Cleanup
- **Priority:** P0
- **Owner Component:** Sandbox Manager (`backend.sandbox.manager`)
- **Description:** Upon completion, failure, timeout, or cancellation of an evaluation, the system SHALL guarantee the immediate removal of all ephemeral Docker containers, custom bridge networks, and temporary scratch directories.
- **Acceptance Criteria:**
  ```gherkin
  Given an evaluation finishes with status "COMPLETED" or "FAILED"
  When the post-evaluation cleanup routine executes
  Then "docker ps -a" must contain zero residual containers associated with the evaluation_id
  And temporary scratch directories under /tmp/reposcore/* must be deleted
  ```

---

## 5. Result Assembly, Scorecards & Reporting

### FR-036: Canonical Evidence Normalization
- **Title:** Unified Evidence Record Creation
- **Priority:** P0
- **Owner Component:** Evidence Engine (`backend.evidence.collector`)
- **Description:** The system SHALL normalize findings from all analyzers (Semgrep, Tree-sitter, Ruff, OSV, runtime probes) into the canonical `Evidence` data model, assigning unique UUIDs, categories, severities, and confidence scores.

### FR-037: Score Calculation & Dimension Breakdown
- **Title:** Deterministic Scorecard Assembly
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** The system SHALL compute an overall composite score (0.0 to 100.0), a corresponding letter grade (A+, A, B, C, D, F), and 10 individual dimension scores backed by itemized deduction receipts referencing specific `evidence_id` records.

### FR-038: Itemized Deduction & Credit Receipts
- **Title:** Transparent Scoring Receipt Generation
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** For every dimension, the system SHALL store the exact mathematical deductions and credits, identifying the rule triggered, points deducted, and linked evidence items.

### FR-039: AI Executive Summary Synthesis
- **Title:** AI Qualitative Summary
- **Priority:** P1
- **Owner Component:** AI Subsystem (`backend.ai.interpreter`)
- **Description:** The system SHALL invoke the AI provider to synthesize an executive summary of the evaluation, highlighting top engineering strengths, critical risks, and architectural observations.

### FR-040: Prioritized Actionable Recommendations
- **Title:** Remediation Recommendation Generation
- **Priority:** P1
- **Owner Component:** AI Subsystem (`backend.ai.interpreter`)
- **Description:** The system SHALL generate a prioritized list of actionable remediation steps (High, Medium, Low priority) linking each recommendation to detected evidence items and vulnerable files.

### FR-041: Evaluation Score History & Diffing
- **Title:** Cross-Commit Regression Tracking
- **Priority:** P1
- **Owner Component:** Reporting Subsystem (`backend.repository.store`)
- **Description:** The system SHALL expose historical evaluations for a given repository, computing score deltas and newly introduced or resolved security findings across commit SHAs.

### FR-042: Markdown Report Generation
- **Title:** Portable Markdown Evaluation Export
- **Priority:** P2
- **Owner Component:** Reporting Subsystem (`backend.reporting.export`)
- **Description:** The system SHALL generate a downloadable GitHub-flavored Markdown report (`REPORT.md`) summarizing scorecard, evidence, runtime diagnostics, and AI recommendations.

### FR-043: JSON Export Contract
- **Title:** Machine-Readable Export
- **Priority:** P1
- **Owner Component:** API Layer (`backend.api.endpoints`)
- **Description:** The system SHALL provide a full, structured JSON export conforming to OpenAPI 3.1 schemas for integration into external CI/CD pipelines.

### FR-044: Finding De-duplication
- **Title:** Multi-Tool Finding Deduplication
- **Priority:** P1
- **Owner Component:** Evidence Engine (`backend.evidence.collector`)
- **Description:** If multiple static analyzers identify identical vulnerabilities on the same file and line (e.g., Bandit and Semgrep both detecting SQL injection), the system SHALL merge them into a single canonical evidence item while crediting both tools as sources.

### FR-045: Audit Trail Immutability
- **Title:** Permanent Record Protection
- **Priority:** P0
- **Owner Component:** Persistence Layer (`backend.database.core`)
- **Description:** Once an evaluation reaches a terminal state (`COMPLETED`, `PARTIALLY_COMPLETED`, `FAILED`, `CANCELLED`, `UNSUPPORTED`), its scores, evidence, runtime observations, and step logs SHALL become strictly immutable in the database.
- **Acceptance Criteria:**
  ```gherkin
  Given an evaluation is in state "COMPLETED"
  When an UPDATE query attempts to alter the composite score or evidence records
  Then the database or application layer must reject the modification with an integrity error
  ```
