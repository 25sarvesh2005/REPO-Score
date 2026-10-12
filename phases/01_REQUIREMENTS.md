# Phase 01 — Requirements Engineering

## RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine

**Phase:** 01  
**Phase Type:** Requirements Engineering  
**Previous Phase:** Phase 00 — Architecture  
**Implementation Status:** PROHIBITED in this phase  
**Required Commit:** `phase(01): establish software requirements`

---

## 1. Phase Objective

Transform the architecture established in Phase 00 into a complete, testable, traceable Software Requirements Specification for RepoScore.

RepoScore must evaluate repositories based on evidence rather than appearance.

> **Core principle:** Do not merely analyze what the code looks like. Determine what the software actually does.

This phase defines **what the system must do**, its constraints, security requirements, evaluation behavior, scoring requirements, AI boundaries, failure semantics, API expectations, persistence requirements, observability requirements, and MVP scope.

This phase MUST NOT implement production functionality.

---

## 2. Mandatory Pre-Phase Audit

Before creating or modifying Phase 01 documentation, the agent MUST read and understand:

- `/AGENTS.md`
- `/phases/00_ARCHITECTURE.md`
- all files under `/docs/architecture/`
- all Architecture Decision Records
- `/docs/phase-reports/PHASE_00.md`
- the current Git state
- the latest Phase 00 commit

The agent MUST verify that the expected previous phase commit exists:

```text
phase(00): establish system architecture
```

The agent MUST inspect:

```bash
git status
git log --oneline --decorate -10
git diff
```

If Phase 00 is incomplete, inconsistent, corrupted, or its architectural rules have been violated:

1. STOP Phase 01 work.
2. Repair the Phase 00 regression.
3. Re-run relevant checks.
4. Document the repair.
5. Only then continue Phase 01.

The agent MUST NOT silently work around broken architecture.

---

## 3. Architecture Regression Check

Before defining requirements, verify that the following architectural decisions remain intact:

- Modular monolith architecture
- Isolated worker execution
- PostgreSQL persistence
- Redis job queue
- Docker-based initial sandbox
- Immutable repository snapshots
- Evidence-first evaluation
- Deterministic scoring
- Analyzer adapter architecture
- Runtime evaluator architecture
- Local-first AI provider architecture
- AI is not the source of truth
- Untrusted repository content is treated as hostile
- Untrusted code is never intentionally executed directly on the host

Any requirement that contradicts Phase 00 MUST be rejected or must trigger a formal ADR update.

---

# 4. Required Deliverables

Create the following files:

```text
docs/
└── requirements/
    ├── SRS.md
    ├── FUNCTIONAL_REQUIREMENTS.md
    ├── NON_FUNCTIONAL_REQUIREMENTS.md
    ├── SECURITY_REQUIREMENTS.md
    ├── API_REQUIREMENTS.md
    ├── EVALUATION_REQUIREMENTS.md
    ├── SCORING_REQUIREMENTS.md
    ├── AI_REQUIREMENTS.md
    ├── MVP_SCOPE.md
    ├── OUT_OF_SCOPE.md
    └── TRACEABILITY_MATRIX.md

docs/
└── phase-reports/
    └── PHASE_01.md
```

Requirements MUST use stable identifiers.

Examples:

```text
FR-001
NFR-001
SEC-001
API-001
EVAL-001
SCORE-001
AI-001
```

Identifiers MUST NOT be casually renumbered after they are introduced.

---

# 5. System Actors

The requirements must define at minimum the following actors.

## 5.1 User

A person submitting a repository for evaluation and reviewing its results.

The user must be able to:

- submit a supported GitHub repository
- start an evaluation
- monitor evaluation progress
- inspect failures
- inspect findings
- inspect evidence
- inspect runtime observations
- inspect security findings
- inspect score dimensions
- inspect AI-generated explanations
- inspect evaluation history
- cancel eligible evaluations

---

## 5.2 Evaluation Worker

A trusted RepoScore worker responsible for executing evaluation jobs.

It coordinates:

- repository processing
- analyzers
- sandbox lifecycle
- runtime evaluation
- evidence collection
- scoring
- AI interpretation

Workers MUST NOT trust repository content.

---

## 5.3 Sandbox

The isolated execution environment used for potentially hostile repository code.

The sandbox must enforce configured resource and security restrictions and expose controlled execution results to RepoScore.

---

## 5.4 AI Provider

An AI system used only for permitted reasoning and interpretation tasks.

Supported conceptual providers:

- LocalProvider
- ExternalProvider
- MockProvider

The core product MUST remain usable without requiring a paid AI service.

---

## 5.5 GitHub

Initial external repository source.

RepoScore must obtain repository source and metadata through controlled Git/GitHub integrations.

GitHub content MUST be treated as untrusted input.

---

## 5.6 Security Intelligence Sources

External or local sources used to identify dependency and security risks.

Examples may include:

- OSV
- Trivy databases
- language ecosystem advisory sources
- open-source security analyzers

These sources provide evidence, not final scores.

---

# 6. Primary User Journeys

## 6.1 Submit Repository

The user submits a GitHub repository.

The system must:

1. validate the repository reference
2. create or identify the repository entity
3. create an immutable evaluation snapshot
4. record ingestion metadata
5. enqueue an evaluation
6. expose evaluation status

---

## 6.2 Monitor Evaluation

The user must be able to observe the current evaluation state.

Example state progression:

```text
QUEUED
→ INGESTING
→ ANALYZING
→ BUILDING
→ STARTING
→ TESTING
→ OBSERVING
→ SCORING
→ AI_INTERPRETATION
→ COMPLETED
```

The system must expose meaningful intermediate states rather than presenting a long-running evaluation as an opaque request.

---

## 6.3 Review Results

After sufficient evaluation work has completed, the user must be able to inspect:

- overall score
- score dimensions
- evidence
- static findings
- security findings
- runtime behavior
- test results
- failures
- resource observations
- AI explanations
- recommendations
- evaluation metadata
- scoring version

---

## 6.4 Failed Evaluation

When evaluation cannot complete normally, the user must receive a structured failure state.

The system must distinguish failures such as:

- repository ingestion failure
- unsupported repository
- build failure
- startup failure
- runtime failure
- analyzer failure
- timeout
- sandbox failure
- cancellation
- AI interpretation failure

A failure MUST NOT be silently represented as success.

---

# 7. Functional Requirements

The detailed functional requirements belong in:

```text
docs/requirements/FUNCTIONAL_REQUIREMENTS.md
```

At minimum, define requirements for the following domains.

---

## 7.1 Repository Ingestion

Requirements must cover:

- GitHub repository submission
- repository URL/reference validation
- cloning/fetching
- commit resolution
- immutable snapshot identity
- default branch detection
- repository metadata capture
- repository size handling
- submodule policy
- Git LFS policy
- authentication boundaries for future private repository support
- clone timeout
- ingestion failure reporting
- duplicate snapshot detection where appropriate

Example:

```text
FR-001
The system SHALL create an immutable repository snapshot associated with the exact commit evaluated.
```

---

## 7.2 Technology Detection

The system must identify relevant repository technologies using deterministic evidence where possible.

Detection may include:

- languages
- package managers
- frameworks
- build systems
- runtime systems
- test frameworks
- container configuration
- application type

Detection confidence must be represented when ambiguity exists.

---

## 7.3 Repository Classification

RepoScore must classify repositories into supported evaluator categories.

Initial conceptual categories include:

- Python application
- Node.js application
- Java application
- REST API
- CLI application
- library/package
- unsupported/unknown

Classification must not assume every repository exposes an HTTP server.

---

# 8. Static Analysis Requirements

Static analysis must operate through analyzer abstractions.

Conceptual hierarchy:

```text
Analyzer
├── LanguageAnalyzer
├── SecurityAnalyzer
├── ComplexityAnalyzer
├── DependencyAnalyzer
├── TestAnalyzer
└── ArchitectureAnalyzer
```

Requirements must cover:

- analyzer discovery
- analyzer selection
- analyzer execution
- analyzer timeout
- analyzer failure isolation
- normalized findings
- source location
- severity
- confidence
- raw result preservation where safe
- tool/version traceability

Potential free/open-source tools include:

- Tree-sitter
- Semgrep
- Ruff
- Bandit
- mypy
- ESLint
- language-specific analyzers

RepoScore MUST NOT depend architecturally on one specific analyzer implementation.

---

# 9. Security Analysis Requirements

Security analysis requirements must include:

- source-code security findings
- dependency vulnerability detection
- dependency health
- unsafe configuration detection
- secret exposure detection where supported
- dangerous execution patterns
- container-related findings where applicable

Potential sources/tools:

- OSV
- Trivy
- Semgrep
- Bandit
- ecosystem-specific tools

Security findings must become normalized evidence.

---

# 10. Sandbox Requirements

The sandbox is a critical security boundary.

All execution of untrusted repository code must occur inside an approved isolated environment.

Initial implementation target:

```text
Docker
```

The architecture must permit stronger isolation technologies later.

Requirements must address:

- CPU limits
- memory limits
- process/PID limits
- execution timeout
- disk/storage limits
- controlled filesystem access
- controlled network access
- non-root execution where feasible
- Linux capability restrictions
- secret isolation
- environment variable filtering
- output capture
- resource metrics
- deterministic cleanup
- orphan process cleanup
- container termination
- sandbox lifecycle logging

Docker MUST NOT be described as an absolute security boundary against highly hostile workloads.

---

# 11. Threat Model Requirements

The requirements must explicitly consider hostile repositories.

Threats include:

- arbitrary code execution
- container escape attempts
- malicious dependencies
- fork bombs
- process exhaustion
- memory exhaustion
- CPU exhaustion
- disk exhaustion
- network abuse
- SSRF
- path traversal
- command injection
- secret theft
- malicious Dockerfiles
- malicious CI configurations
- malicious build scripts
- malicious test suites
- Git hooks
- prompt injection
- output flooding
- intentionally hanging processes

Detailed security specifications belong in Phase 02, but Phase 01 must establish the requirements and boundaries.

---

# 12. Build Requirements

The evaluation engine must determine whether a repository can be prepared and built under its detected technology profile.

Requirements must define:

- build strategy selection
- dependency installation
- build timeout
- build output capture
- build exit status
- build failure classification
- unsupported build handling
- dependency installation failure
- reproducibility metadata
- sandbox-only execution

A failed build must generate evidence.

---

# 13. Startup Requirements

For runnable applications, RepoScore must determine whether the application starts successfully.

Requirements must include:

- startup command selection
- startup timeout
- process health detection
- crash detection
- stderr/stdout capture
- exit-code capture
- port/service discovery where applicable
- structured startup failure evidence

Startup success must not be inferred solely from process creation.

---

# 14. Runtime Evaluation Requirements

Runtime evaluation must support repository-specific evaluator types.

The runtime engine must capture evidence such as:

- stdout
- stderr
- exit code
- exceptions
- crashes
- HTTP response status where applicable
- response payload metadata where safe
- execution latency
- CPU usage
- memory usage
- process behavior
- test result
- timeout
- abnormal termination

Runtime evaluation must not assume HTTP semantics for all repositories.

---

# 15. Testing Requirements

RepoScore must distinguish test origins.

At minimum:

```text
REPOSITORY_PROVIDED
PLATFORM_DETERMINISTIC
AI_GENERATED
RUNTIME_SCENARIO
SECURITY
```

Each test result must record its origin.

Generated tests must:

- be clearly labeled AI-generated
- be traceable to the generation request/model/prompt version where applicable
- execute only in the sandbox
- never silently replace deterministic platform tests
- not be treated as ground truth without evidence
- expose failures and uncertainty

---

# 16. Runtime Observation Requirements

The platform must collect observable runtime behavior where supported.

Examples:

- process lifecycle
- execution duration
- CPU consumption
- memory consumption
- exit status
- application crashes
- test behavior
- service responsiveness
- timeout behavior

Runtime observations must become structured evidence.

---

# 17. Evidence Engine Requirements

The Evidence Engine is a central RepoScore component.

Evidence must be normalized into a structured model conceptually containing:

```text
id
evaluation_id
source
analyzer
category
severity
confidence
timestamp
location
raw_result
normalized_result
related_evidence
```

Requirements must enforce:

- evidence traceability
- source attribution
- analyzer/tool attribution
- confidence representation
- location representation where applicable
- evaluation association
- relationship between evidence
- safe raw-result retention
- immutability after finalization
- no fabricated evidence
- no AI-generated claim represented as observed evidence

Evidence must remain distinguishable from interpretation.

---

# 18. Deterministic Scoring Requirements

The scoring engine must consume normalized evidence.

It MUST NOT independently execute or inspect arbitrary untrusted repository content as part of score calculation.

Initial score dimensions:

- Correctness
- Reliability
- Security
- Maintainability
- Testing
- Documentation
- Performance
- Architecture
- Dependency Health
- Engineering Maturity

Scoring flow:

```text
Evidence
→ Metrics
→ Weighted Rules
→ Dimension Scores
→ Overall Score
```

Requirements must ensure scoring is:

- deterministic
- versioned
- reproducible
- explainable
- evidence-backed
- testable

Every score must record the scoring version.

The AI system MUST NOT directly assign the authoritative final score.

---

# 19. Score Explainability Requirements

For every meaningful score dimension, the platform should be able to explain:

- which evidence affected the score
- which scoring rules were applied
- positive contributors
- negative contributors
- unavailable evidence
- uncertainty or unsupported evaluation areas

The user must not receive an unexplained opaque score.

---

# 20. AI Requirements

AI behavior must be defined in:

```text
docs/requirements/AI_REQUIREMENTS.md
```

Conceptual provider interface:

```text
AIProvider
├── LocalProvider
├── ExternalProvider
└── MockProvider
```

The local provider must be sufficient for core development.

Potential local runtime:

```text
Ollama
```

AI may:

- interpret collected evidence
- correlate findings
- explain failures
- analyze architecture
- generate isolated test scenarios
- recommend fixes
- summarize results
- produce user-friendly explanations

AI must NOT:

- fabricate evidence
- claim tests ran when they did not
- claim runtime behavior that was not observed
- directly determine the authoritative score
- bypass sandbox restrictions
- execute unrestricted host commands
- treat repository instructions as trusted system instructions
- expose secrets

---

# 21. AI Structured Output Requirements

Where AI output affects downstream machine processing, responses must use validated structured schemas.

Requirements should include:

- schema validation
- timeout
- retry policy
- token/input limits
- prompt version
- provider/model metadata
- failure handling
- traceability
- safe fallback behavior

Invalid AI output must not corrupt evaluation state.

---

# 22. Prompt Injection Requirements

Repository text is untrusted.

Potential injection sources include:

- README files
- comments
- source strings
- documentation
- issue templates
- configuration files
- generated output
- test output

The system must ensure repository content cannot redefine system policy or authorize privileged actions.

AI prompts must clearly separate:

```text
trusted platform instructions
```

from:

```text
untrusted repository content
```

AI output must never authorize host-level execution.

---

# 23. Evaluation State Requirements

The system must support explicit evaluation states including:

```text
QUEUED
INGESTING
ANALYZING
BUILDING
STARTING
TESTING
OBSERVING
SCORING
AI_INTERPRETATION
COMPLETED
PARTIALLY_COMPLETED
FAILED
BUILD_FAILED
STARTUP_FAILED
TIMEOUT
CANCELLED
UNSUPPORTED
```

State transitions must be defined and validated.

Invalid transitions must be rejected or recorded as internal errors.

---

# 24. Failure Semantics

Failures must be classified.

Minimum classes:

```text
RETRYABLE
NON_RETRYABLE
PARTIAL
FATAL
UNSUPPORTED
TIMEOUT
CANCELLED
```

Requirements:

- no silent failures
- no infinite retries
- no converting failures into success
- failures must retain diagnostic evidence
- retry attempts must be bounded
- partial evaluation must be distinguishable from complete evaluation

---

# 25. API Requirements

Define requirements for at least the following logical endpoints.

```http
POST /repositories
POST /evaluations

GET /evaluations/{id}
GET /evaluations/{id}/status
GET /evaluations/{id}/score
GET /evaluations/{id}/findings
GET /evaluations/{id}/evidence
GET /evaluations/{id}/runtime
GET /evaluations/{id}/security
GET /evaluations/{id}/history

POST /evaluations/{id}/cancel
```

Also define requirements for:

- health endpoint
- readiness endpoint
- structured errors
- request validation
- response validation
- pagination where appropriate
- API versioning strategy
- correlation IDs
- idempotency where required
- authentication boundary for future phases

Phase 01 defines requirements only.

It MUST NOT implement these endpoints.

---

# 26. Persistence Requirements

The requirements must account for the conceptual entities established in Phase 00:

```text
Repository
RepositorySnapshot
Evaluation
EvaluationStep
ExecutionEnvironment
TestScenario
RuntimeObservation
StaticFinding
SecurityFinding
Evidence
Score
ScoreDimension
Recommendation
AIAnalysis
EvaluationEvent
```

Requirements must define:

- identifiers
- ownership/relationships
- lifecycle expectations
- auditability
- timestamps
- immutable fields
- deletion/retention considerations
- evaluation history
- scoring version
- analyzer metadata
- snapshot identity

Detailed schema design belongs to Phase 03.

---

# 27. Internal Event Requirements

RepoScore should expose internal lifecycle events conceptually including:

```text
repository.created
repository.ingested
evaluation.created
evaluation.started
evaluation.step.started
evaluation.step.completed
evaluation.step.failed
sandbox.created
sandbox.started
sandbox.finished
analysis.completed
runtime.test.started
runtime.test.completed
evidence.created
score.calculated
ai.analysis.started
ai.analysis.completed
evaluation.completed
evaluation.failed
```

Requirements must define event purpose and minimum metadata without prematurely implementing an event bus.

---

# 28. Observability Requirements

Every evaluation must have a correlation identifier.

The platform must support measurement of:

- total evaluation duration
- queue latency
- ingestion duration
- analyzer duration
- build duration
- startup duration
- test duration
- sandbox duration
- AI duration
- worker failures
- API latency
- resource consumption
- evaluation success/failure rate

Logs must be structured.

Logs MUST NOT intentionally contain:

- access tokens
- private keys
- repository credentials
- passwords
- sensitive environment variables
- authentication secrets

---

# 29. Frontend Requirements

The frontend requirements should cover a minimal usable evaluation workflow.

The user interface should eventually support:

- repository submission
- evaluation status
- progress/stage visualization
- overall score
- dimension scores
- findings
- evidence
- runtime observations
- security findings
- recommendations
- AI explanation
- failure diagnostics
- evaluation history

The frontend target architecture is:

```text
Next.js
TypeScript
```

Phase 01 MUST NOT implement the frontend.

---

# 30. Non-Functional Requirements

Define all major NFRs in:

```text
docs/requirements/NON_FUNCTIONAL_REQUIREMENTS.md
```

At minimum cover:

- security
- reliability
- maintainability
- scalability
- performance
- observability
- reproducibility
- portability
- testability
- extensibility
- usability
- accessibility
- recoverability
- data integrity

Use identifiers:

```text
NFR-001
NFR-002
...
```

Do not invent arbitrary performance promises.

Where benchmarks are required, use:

```text
TBD — benchmark required
```

and define how the target will later be measured.

---

# 31. Security Requirements

Define detailed high-level security requirements using:

```text
SEC-001
SEC-002
...
```

Requirements must include:

- hostile repository handling
- sandbox-only execution
- least privilege
- secret isolation
- filesystem restrictions
- network restrictions
- resource limits
- timeout enforcement
- dependency risk handling
- command injection prevention
- path traversal prevention
- SSRF controls
- Git hook controls
- Dockerfile risk handling
- output size limits
- log redaction
- prompt injection protection
- cancellation/cleanup guarantees
- future stronger isolation compatibility

Phase 02 will expand these into the formal threat model and sandbox security specification.

---

# 32. Performance Requirements

Performance requirements must be measurable but realistic.

Do NOT invent claims such as:

```text
Every repository must complete evaluation in 30 seconds.
```

Repository evaluation time varies significantly.

Instead define metrics such as:

- API response latency
- queue latency
- sandbox startup latency
- analyzer execution duration
- evaluation duration by repository size/category
- maximum configured evaluation timeout
- resource usage

If a target has not been benchmarked:

```text
TBD — benchmark required
```

must be used.

---

# 33. Compatibility Requirements

Define supported, partially supported, and unsupported categories.

Example:

```text
SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
UNKNOWN
```

Initial MVP technology support should be deliberately narrow enough to be reliable.

The requirements should allow additional languages and evaluators to be added through adapters later.

---

# 34. MVP Scope

Define the MVP in:

```text
docs/requirements/MVP_SCOPE.md
```

The minimum meaningful RepoScore vertical slice is:

```text
GitHub ingestion
→ immutable repository snapshot
→ technology detection
→ static analysis
→ Docker sandbox
→ build attempt
→ runtime execution where supported
→ deterministic evidence
→ basic deterministic scoring
→ AI explanation
→ evaluation report
```

The MVP must prove the core thesis:

> RepoScore evaluates software using observable and traceable evidence rather than superficial repository metadata alone.

---

# 35. Out of Scope

Create:

```text
docs/requirements/OUT_OF_SCOPE.md
```

Potential initial exclusions should be explicitly documented.

Examples may include:

- arbitrary cloud infrastructure deployment
- production deployment of evaluated repositories
- unrestricted internet access from sandboxes
- fully autonomous code modification
- guaranteed malware containment against advanced container escapes
- every programming language
- every build system
- every repository type
- enterprise SSO
- billing
- marketplace features
- large-scale distributed worker fleets
- full private-repository support unless separately approved

Out-of-scope items must not be accidentally implemented during early phases.

---

# 36. Requirement Priorities

Each requirement should receive a priority.

Use:

```text
P0 — required for core correctness/security/MVP
P1 — important for MVP quality
P2 — valuable after core MVP
P3 — future enhancement
```

Security boundaries required to safely execute untrusted code are P0.

Evidence integrity and deterministic scoring are P0.

---

# 37. Acceptance Criteria

Critical requirements must include acceptance criteria.

Preferred format:

```gherkin
Given ...
When ...
Then ...
```

Example:

```gherkin
Given a repository evaluation is associated with commit ABC
When the upstream repository receives a new commit DEF
Then the existing evaluation must continue to reference the immutable ABC snapshot
```

Another example:

```gherkin
Given an untrusted repository contains a malicious build command
When RepoScore evaluates the repository
Then the command must not be intentionally executed directly on the host
And any allowed execution must occur through the approved sandbox boundary
```

Acceptance criteria must be specific enough to become tests in later phases.

---

# 38. Requirement Traceability Matrix

Create:

```text
docs/requirements/TRACEABILITY_MATRIX.md
```

The matrix must conceptually map:

| Requirement | Architecture Component | Implementation Phase | Test | Evidence |
|---|---|---|---|---|
| FR-001 | Repository Manager | Phase 06 | TBD | Repository snapshot |
| SEC-001 | Sandbox Manager | Phase 07 | TBD | Sandbox execution record |
| SCORE-001 | Scoring Engine | Phase 10 | TBD | Score calculation record |

Every P0 requirement must have:

- architecture owner/component
- planned implementation phase
- planned validation/test
- expected evidence

The matrix must be updated in future phases rather than recreated.

---

# 39. Planned Implementation Phase Mapping

Use the current project phase sequence:

```text
00 Architecture
01 Requirements
02 Security
03 Data Model
04 API Contract
05 Foundation
06 Repository Ingestion
07 Sandbox
08 Static Analysis
09 Runtime Engine
10 Scoring Engine
11 AI Engine
12 Dashboard
13 Integration
14 Adversarial Testing
15 CI/CD
16 Observability
17 Hardening
18 Final Audit
```

Phase 01 requirements must map forward to these phases.

Do not change phase numbering without an explicit architecture/project governance decision.

---

# 40. SRS Requirements

Create:

```text
docs/requirements/SRS.md
```

It should serve as the master requirements document and include:

1. Purpose
2. Product vision
3. Scope
4. Definitions
5. Actors
6. Assumptions
7. Constraints
8. User journeys
9. Functional requirement index
10. Non-functional requirement index
11. Security requirement index
12. Evaluation requirements
13. Scoring requirements
14. AI requirements
15. API requirements
16. Data/persistence requirements
17. Failure semantics
18. MVP scope
19. Out-of-scope summary
20. Requirement traceability
21. Acceptance criteria strategy
22. Open questions/TBDs

The SRS may reference detailed requirement files instead of duplicating every requirement.

---

# 41. Requirement Quality Rules

Every requirement should be:

- necessary
- unambiguous
- testable
- traceable
- implementation-neutral where appropriate
- consistent with architecture
- uniquely identified
- prioritized

Avoid vague statements such as:

```text
The system should be fast.
```

Prefer:

```text
NFR-XXX
The system SHALL record evaluation stage duration so performance can be benchmarked by repository category.
```

---

# 42. No Fake Precision

Do not invent unsupported numeric thresholds merely to make the requirements appear complete.

For unresolved values, write:

```text
TBD — requires benchmarking
```

or:

```text
TBD — requires security validation
```

The unresolved requirement must be tracked.

---

# 43. No Implementation During Phase 01

The agent MUST NOT implement:

- FastAPI routes
- SQLAlchemy models
- Alembic migrations
- Redis workers
- Docker sandbox runtime
- analyzers
- scoring code
- AI integration
- frontend components
- GitHub Actions pipelines

Small documentation-supporting examples are acceptable.

Production implementation is not.

---

# 44. Quality Review

Before completing Phase 01, the agent must perform a documentation review.

Verify:

- all required files exist
- requirement IDs are unique
- no conflicting requirements exist
- no requirement violates Phase 00
- P0 requirements have acceptance criteria where appropriate
- security boundaries are explicit
- AI boundaries are explicit
- scoring remains deterministic
- evidence remains source-of-truth
- untrusted execution remains sandboxed
- unsupported behavior is explicit
- failure states are explicit
- MVP scope is coherent
- out-of-scope items are documented
- traceability matrix exists
- unresolved items are marked TBD rather than guessed

---

# 45. Architecture Regression Review

Before commit, compare Phase 01 requirements against:

```text
/phases/00_ARCHITECTURE.md
/docs/architecture/*
```

Check specifically for accidental architecture drift.

Examples of forbidden drift:

- AI becomes authoritative scorer
- untrusted code executes on host
- evidence can be fabricated by AI
- repository snapshots become mutable
- API directly performs long-running evaluations synchronously
- analyzer implementations become tightly coupled to orchestration
- scoring directly runs repository code
- paid external AI becomes mandatory
- Docker is claimed to provide perfect isolation

Any architecture change requires an ADR.

---

# 46. Phase Report

Create:

```text
docs/phase-reports/PHASE_01.md
```

It must include:

```text
Phase
Status
Start state
Previous commit reviewed
Architecture audit result
Files created
Files modified
Requirement counts by category
P0/P1/P2/P3 counts
TBD/open question count
Architecture deviations
Regression fixes performed
Validation performed
Known limitations
Next phase
Commit SHA
```

Do not fabricate the commit SHA before committing.

---

# 47. Phase Acceptance Gate

Phase 01 is complete only if:

- Phase 00 was audited
- previous regressions were repaired
- SRS exists
- functional requirements exist
- non-functional requirements exist
- security requirements exist
- API requirements exist
- evaluation requirements exist
- scoring requirements exist
- AI requirements exist
- MVP scope exists
- out-of-scope document exists
- traceability matrix exists
- requirement IDs are unique
- critical requirements have acceptance criteria
- requirements are consistent with architecture
- no production implementation was introduced
- phase report exists
- repository is ready to commit

If any acceptance condition fails, DO NOT mark the phase complete.

---

# 48. Commit Procedure

Before committing:

```bash
git status
git diff --check
git diff
```

Run any documentation validation or repository checks that already exist.

Do not bypass failing existing checks.

Commit using exactly:

```bash
git add .
git commit -m "phase(01): establish software requirements"
```

After commit:

```bash
git status
git log -1 --oneline
```

The working tree should be clean.

Record the resulting commit SHA in:

```text
docs/phase-reports/PHASE_01.md
```

If recording the SHA requires a follow-up documentation commit, follow the repository's established governance procedure without rewriting unrelated history.

---

# 49. Handoff to Phase 02

Phase 02 is:

```text
Security / Threat Model & Sandbox Security Specification
```

Phase 02 must begin by reading:

- `/AGENTS.md`
- Phase 00
- Phase 01
- all architecture documentation
- all requirements documentation
- Phase 00 and Phase 01 reports
- latest Git history

It must audit the current repository before making changes.

Phase 02 must expand the security requirements into a formal threat model and detailed sandbox/security specification without weakening the requirements established here.

---

# 50. Final Phase Rule

The Phase 01 agent must preserve the following hierarchy:

```text
Correctness > speed
Security > convenience
Evidence > assumptions
Tests > claims
Determinism > opaque judgment
Traceability > undocumented behavior
```

The output of this phase must make future implementation agents capable of answering:

> What exactly must RepoScore do, why must it do it, where will it be implemented, and how will we prove that it works?

If that cannot be answered from the requirements and traceability documents, Phase 01 is incomplete.
