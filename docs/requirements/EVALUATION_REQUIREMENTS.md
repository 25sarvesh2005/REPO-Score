# Evaluation Lifecycle & Runtime Requirements (EVAL)

> **Document:** `EVALUATION_REQUIREMENTS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Requirements Baseline  
> **Phase:** Phase 01 — Requirements Engineering  
> **Authority:** `phases/01_REQUIREMENTS.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Domain Overview

The Evaluation Subsystem coordinates the entire technical analysis of a repository, from static inspection to isolated runtime execution and evidence assembly:
1. **Lifecycle State Machine & Invariants** (`EVAL-001` to `EVAL-005`)
2. **Static Analysis & Linters** (`EVAL-006` to `EVAL-010`)
3. **Dependency & Security Vulnerability Auditing** (`EVAL-011` to `EVAL-015`)
4. **Sandbox Management & Lifecycle** (`EVAL-016` to `EVAL-020`)
5. **Build Evaluation** (`EVAL-021` to `EVAL-024`)
6. **Application Startup & Readiness Probing** (`EVAL-025` to `EVAL-028`)
7. **Runtime Testing & Synthetic Probing** (`EVAL-029` to `EVAL-032`)
8. **Evidence Engine Normalization** (`EVAL-033` to `EVAL-036`)
9. **Failure Semantics & Taxonomy** (`EVAL-037` to `EVAL-040`)

---

## 2. Evaluation Lifecycle State Machine

### EVAL-001: 17-State Finite State Machine Conformance
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** Every evaluation MUST progress through the approved 17-state finite state machine (FSM):
  `QUEUED`, `INGESTING`, `ANALYZING`, `BUILDING`, `STARTING`, `TESTING`, `OBSERVING`, `SCORING`, `AI_INTERPRETATION`, `COMPLETED`, `PARTIALLY_COMPLETED`, `BUILD_FAILED`, `STARTUP_FAILED`, `FAILED`, `TIMEOUT`, `CANCELLED`, `UNSUPPORTED`.
- **Acceptance Criteria:**
  ```gherkin
  Given an evaluation is created
  When it transitions through stages
  Then every transition must match the permitted transition table in EVALUATION_LIFECYCLE.md
  And any invalid transition attempt must raise an IllegalStateTransitionError
  ```

### EVAL-002: Atomic Step Audit Logging
- **Priority:** P0
- **Owner Component:** Orchestration Layer (`backend.orchestration.engine`)
- **Description:** Every state transition MUST create an atomic row in `evaluation_steps` with: `step_name`, `started_at`, `completed_at`, `status` (`SUCCESS`, `FAILURE`, `SKIPPED`), `exit_code`, and `error_message`.

### EVAL-003: Terminal State Immutability
- **Priority:** P0
- **Owner Component:** Orchestration Layer (`backend.orchestration.engine`)
- **Description:** Once an evaluation reaches a terminal state (`COMPLETED`, `PARTIALLY_COMPLETED`, `FAILED`, `CANCELLED`, `UNSUPPORTED`), its status MUST NEVER transition to any other state.

### EVAL-004: Graceful Degradation on Build Failure
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** If a repository fails compilation or dependency installation during `BUILDING`, the orchestrator SHALL set status to `BUILD_FAILED`, record the stderr compiler output as negative evidence, route directly to `SCORING`, and finalize in `PARTIALLY_COMPLETED`.
- **Acceptance Criteria:**
  ```gherkin
  Given a repository that fails "pip install" due to missing C headers
  When the build step completes with non-zero exit code
  Then the orchestrator must transition to "BUILD_FAILED"
  And route directly to "SCORING"
  And the evaluation must finish in "PARTIALLY_COMPLETED"
  And static analysis findings must remain fully preserved
  ```

### EVAL-005: Graceful Degradation on Startup Failure
- **Priority:** P0
- **Owner Component:** Evaluation Orchestrator (`backend.orchestration.engine`)
- **Description:** If an application crashes on startup or fails to bind to its port within the configured timeout during `STARTING`, the orchestrator SHALL set status to `STARTUP_FAILED`, capture crash traces as negative evidence, route to `SCORING`, and finalize in `PARTIALLY_COMPLETED`.

---

## 3. Static Analysis & Linters

### EVAL-006: Pluggable Analyzer Protocol (`IAnalyzer`)
- **Priority:** P0
- **Owner Component:** Static Analyzer Subsystem (`backend.analyzers.core`)
- **Description:** All static analyzers MUST implement the Python `IAnalyzer` protocol, accepting a repository snapshot path and configuration, and returning a typed list of `NormalizedFinding` objects.

### EVAL-007: Tree-sitter Syntax & AST Analysis
- **Priority:** P0
- **Owner Component:** Language Analyzers (`backend.analyzers.treesitter`)
- **Description:** The system SHALL use Tree-sitter to parse source files into ASTs for supported languages, extracting function counts, class hierarchies, cyclomatic complexity, cognitive complexity, and syntax errors.

### EVAL-008: Semgrep Pattern & Security Rule Execution
- **Priority:** P0
- **Owner Component:** Security Analyzers (`backend.analyzers.semgrep`)
- **Description:** The system SHALL execute Semgrep rulesets (OWASP Top 10, security audit rules, dangerous function calls) against repository source files, mapping rule violations to line numbers and severity levels.

### EVAL-009: Ecosystem-Specific Linters (Ruff, ESLint)
- **Priority:** P1
- **Owner Component:** Linter Analyzers (`backend.analyzers.linters`)
- **Description:** The system SHALL invoke fast, open-source linters where applicable:
  - Python: `Ruff` for style, import hygiene, and code formatting violations
  - Node.js: `ESLint` config inspection and static linting

### EVAL-010: Static Analysis Isolation & Timeout
- **Priority:** P0
- **Owner Component:** Static Analyzer Subsystem (`backend.analyzers.core`)
- **Description:** Static analyzers SHALL execute in bounded subprocesses with a timeout of 180 seconds. A hanging or crashed analyzer MUST be isolated, recorded as a step warning, and not crash other analyzers.

---

## 4. Dependency & Security Vulnerability Auditing

### EVAL-011: Dependency Manifest & Lockfile Parsing
- **Priority:** P0
- **Owner Component:** Dependency Analyzer (`backend.analyzers.dependencies`)
- **Description:** The system SHALL parse dependencies and pinned versions from `requirements.txt`, `poetry.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, and `pom.xml`.

### EVAL-012: OSV Advisory Querying
- **Priority:** P0
- **Owner Component:** Security Engine (`backend.security.advisories`)
- **Description:** The system SHALL query the Open Source Vulnerabilities (OSV) database using package names and resolved versions to identify known CVEs, severity ratings, and patched versions.
- **Acceptance Criteria:**
  ```gherkin
  Given a requirements.txt with "requests==2.19.1"
  When the OSV scanner queries the package version
  Then it must identify known advisories for that version
  And normalize them into CRITICAL/HIGH security evidence items
  ```

### EVAL-013: Hardcoded Secret Detection
- **Priority:** P0
- **Owner Component:** Security Engine (`backend.security.secrets`)
- **Description:** The system SHALL scan repository files for unencrypted secrets (API keys, private keys, database passwords, JWT tokens) using entropy analysis and regex signatures, masking detected secrets before recording evidence.

### EVAL-014: Dangerous Code Pattern Detection
- **Priority:** P0
- **Owner Component:** Security Engine (`backend.security.code_patterns`)
- **Description:** The system SHALL detect dangerous execution patterns: `eval()`, `exec()`, `os.system()` with unsanitized arguments, deserialization vulnerabilities (`pickle.loads`), and SQL injection patterns.

### EVAL-015: Dependency Health Metrics
- **Priority:** P1
- **Owner Component:** Dependency Analyzer (`backend.analyzers.dependencies`)
- **Description:** The system SHALL evaluate dependency hygiene: unpinned versions, deprecated dependencies, abandoned packages, and dependency bloat ratio.

---

## 5. Sandbox Management & Execution

### EVAL-016: Ephemeral Docker Container Lifecycle
- **Priority:** P0
- **Owner Component:** Sandbox Manager (`backend.sandbox.manager`)
- **Description:** All code execution MUST occur inside ephemeral Docker containers created on-demand for a single evaluation and destroyed immediately upon step completion.

### EVAL-017: Non-Root & Capability Hardening Enforcement
- **Priority:** P0
- **Owner Component:** Sandbox Manager (`backend.sandbox.manager`)
- **Description:** The sandbox manager MUST enforce `--cap-drop=ALL`, `--security-opt=no-new-privileges:true`, `--user=10001:10001`, and `--read-only` on all spawned containers.

### EVAL-018: Ephemeral Scratch Storage Management
- **Priority:** P0
- **Owner Component:** Sandbox Manager (`backend.sandbox.manager`)
- **Description:** The sandbox manager SHALL mount a dedicated tmpfs or ephemeral volume for build artifacts (`/workspace`), enforcing a maximum size of 500MB.

### EVAL-019: cgroups v2 Quota Enforcement
- **Priority:** P0
- **Owner Component:** Sandbox Manager (`backend.sandbox.manager`)
- **Description:** Containers MUST be constrained to 2GB RAM (`--memory=2g`), 2 CPU cores (`--cpus=2.0`), and 128 PIDs (`--pids-limit=128`).

### EVAL-020: Output Stream Buffering & Truncation
- **Priority:** P0
- **Owner Component:** Sandbox Manager (`backend.sandbox.manager`)
- **Description:** Container stdout and stderr streams MUST be captured in real time and capped at 10MB per step, cleanly truncating excess data.

---

## 6. Build Evaluation

### EVAL-021: Build Strategy Resolution
- **Priority:** P0
- **Owner Component:** Build Evaluator (`backend.runtime.builder`)
- **Description:** The system SHALL select the build strategy based on detected technology:
  - Python: `pip install -r requirements.txt` or `poetry install --no-root`
  - Node.js: `npm ci` or `npm install --ignore-scripts`
- **Acceptance Criteria:**
  ```gherkin
  Given a Python repository containing "requirements.txt"
  When the build step is initiated
  Then the sandbox must execute the build command inside the isolated container
  And capture stdout, stderr, and exit code
  ```

### EVAL-022: Package Install Scripts Neutralization
- **Priority:** P0
- **Category:** Security Boundary
- **Description:** For Node.js repositories, package installation SHOULD default to `npm install --ignore-scripts` to neutralize malicious lifecycle scripts (`preinstall`, `postinstall`).

### EVAL-023: Build Timeout Enforcement
- **Priority:** P0
- **Owner Component:** Build Evaluator (`backend.runtime.builder`)
- **Description:** The build step MUST enforce a hard timeout of 300 seconds. If the build does not complete within 300 seconds, the container MUST be terminated and marked `TIMEOUT`.

### EVAL-024: Build Diagnostic Output Capture
- **Priority:** P0
- **Owner Component:** Build Evaluator (`backend.runtime.builder`)
- **Description:** The build evaluator SHALL capture full compiler/installer output, categorize errors (missing dependency, syntax error, incompatible platform), and convert them into evidence items.

---

## 7. Startup & Readiness Probing

### EVAL-025: Application Bootstrapping
- **Priority:** P0
- **Owner Component:** Startup Evaluator (`backend.runtime.startup`)
- **Description:** For runnable applications (`WEB_API`, `BACKGROUND_WORKER`), the system SHALL bootstrap the application in the sandbox using detected entrypoint commands.

### EVAL-026: Service Readiness Probing (HTTP / Port)
- **Priority:** P0
- **Owner Component:** Startup Evaluator (`backend.runtime.startup`)
- **Description:** The system SHALL poll target application listening ports (e.g., 8000, 3000, 8080) and HTTP readiness endpoints (`/health`, `/`, `/docs`) within a 60-second window.
- **Acceptance Criteria:**
  ```gherkin
  Given a FastAPI application started on port 8000
  When the startup evaluator polls "http://sandbox-ip:8000/"
  Then a 200 OK response within 60 seconds must transition the step to SUCCESS
  And the application startup time must be recorded in milliseconds
  ```

### EVAL-027: Crash & Early Exit Detection
- **Priority:** P0
- **Owner Component:** Startup Evaluator (`backend.runtime.startup`)
- **Description:** If the application process terminates prematurely (non-zero exit code, unhandled exception, segmentation fault), the system SHALL immediately capture stderr and transition to `STARTUP_FAILED`.

### EVAL-028: Port Discovery
- **Priority:** P1
- **Owner Component:** Startup Evaluator (`backend.runtime.startup`)
- **Description:** The system SHALL detect application listening ports dynamically by inspecting process network sockets (`netstat` / `/proc/net/tcp`) within the sandbox container.

---

## 8. Runtime Probing, Testing & Telemetry

### EVAL-029: Test Origin Classification
- **Priority:** P0
- **Owner Component:** Runtime Evaluator (`backend.runtime.testing`)
- **Description:** All executed tests MUST be categorized into explicit origins:
  1. `REPOSITORY_PROVIDED`: Native repository test suite (`pytest`, `npm test`)
  2. `PLATFORM_DETERMINISTIC`: Standardized RepoScore synthetic probes (HTTP fuzzing, health checks)
  3. `AI_GENERATED`: Test scenarios generated by LLMs (clearly labeled)
  4. `RUNTIME_SCENARIO`: End-to-end integration scenario
  5. `SECURITY`: Security-specific runtime fuzzing

### EVAL-030: Native Repository Test Suite Execution
- **Priority:** P1
- **Owner Component:** Runtime Evaluator (`backend.runtime.testing`)
- **Description:** If a test runner is detected and safe execution is configured, the system SHALL execute the repository's native test suite inside the network-severed sandbox (`--network none`), capturing test counts, pass/fail rates, and code coverage.

### EVAL-031: Synthetic HTTP Probing
- **Priority:** P0
- **Owner Component:** Runtime Evaluator (`backend.runtime.http_evaluator`)
- **Description:** For `WEB_API` applications, the system SHALL execute synthetic HTTP GET/POST probes against discovered endpoints, recording response status codes, payload sizes, and latency percentiles (p50, p95, p99).

### EVAL-032: Telemetry Sampling (CPU & RAM)
- **Priority:** P1
- **Owner Component:** Runtime Evaluator (`backend.runtime.observer`)
- **Description:** During runtime execution, the system SHALL sample cgroups CPU usage percentage, memory RSS, and peak memory usage at 1-second intervals, computing peak and average consumption.

---

## 9. Evidence Engine Normalization

### EVAL-033: Canonical Evidence Model Structure
- **Priority:** P0
- **Owner Component:** Evidence Engine (`backend.evidence.collector`)
- **Description:** All evidence collected across static analysis, security scans, build logs, and runtime telemetry MUST be normalized into the canonical `Evidence` schema:
  - `id`: UUIDv7
  - `evaluation_id`: UUIDv7
  - `source`: Analyzer or probe identifier
  - `category`: Dimension category (e.g., `SECURITY`, `CORRECTNESS`, `PERFORMANCE`)
  - `severity`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`
  - `confidence`: Float `0.0` to `1.0`
  - `timestamp`: UTC datetime
  - `location`: File path, line start/end, column start/end
  - `raw_result`: Sanitized raw output
  - `normalized_result`: Standardized JSON payload
  - `related_evidence`: Array of related evidence IDs

### EVAL-034: Evidence Immutability Guarantee
- **Priority:** P0
- **Owner Component:** Evidence Engine (`backend.evidence.collector`)
- **Description:** Evidence records MUST be append-only. Once persisted, an evidence record can never be modified or deleted.

### EVAL-035: Multi-Tool Deduplication & Correlation
- **Priority:** P1
- **Owner Component:** Evidence Engine (`backend.evidence.collector`)
- **Description:** When multiple analyzers report the same issue on the same file and line, the system SHALL merge them into a primary evidence record, linking secondary tool findings in `related_evidence`.

### EVAL-036: Fabricated Evidence Prohibition
- **Priority:** P0
- **Category:** Evidence Integrity
- **Description:** The system SHALL NEVER fabricate evidence. AI models and heuristic engines are strictly barred from generating fictitious evidence records that were not observed during actual tool runs or container execution.

---

## 10. Failure Semantics & Taxonomy

### EVAL-037: Structured Failure Classification
- **Priority:** P0
- **Owner Component:** Failure Manager (`backend.orchestration.failure`)
- **Description:** When an evaluation step fails, the system SHALL classify the failure into the standard 7-class taxonomy:
  1. `RETRYABLE`: Transient infrastructure error (e.g. Redis connection timeout, transient Git 503)
  2. `NON_RETRYABLE`: Deterministic code error (e.g. syntax error, compilation failure)
  3. `PARTIAL`: Step failure routing to partial evaluation (`BUILD_FAILED`, `STARTUP_FAILED`)
  4. `FATAL`: Unrecoverable worker or database corruption
  5. `UNSUPPORTED`: Repository exceeds size limits or has unrecognized language
  6. `TIMEOUT`: Execution exceeded step or global timeout budget
  7. `CANCELLED`: Client aborted job

### EVAL-038: Bounded Retry Policy
- **Priority:** P0
- **Owner Component:** Orchestration Layer (`backend.orchestration.engine`)
- **Description:** Only errors classified as `RETRYABLE` may be retried. Maximum retries SHALL be capped at 2 attempts with exponential backoff. Non-retryable errors MUST fail immediately.

### EVAL-039: Diagnostic Trace Retention
- **Priority:** P0
- **Owner Component:** Persistence Layer (`backend.database.core`)
- **Description:** Failed steps MUST retain sanitized stderr output, exit codes, and diagnostic context so users can troubleshoot failures accurately.

### EVAL-040: No Converting Failures into Success
- **Priority:** P0
- **Category:** Integrity
- **Description:** The system SHALL NEVER silently convert a failed step into a success. Partial evaluations MUST be explicitly flagged as `PARTIALLY_COMPLETED`.
