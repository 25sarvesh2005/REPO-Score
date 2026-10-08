# PHASE 00 — ARCHITECTURAL FOUNDATION

> **Status:** Phase 0  
> **Project:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Phase Type:** Architecture only  
> **Implementation Allowed:** NO

---

## 0. AGENT MISSION

You are the **Principal Software Architect, Security Architect, Distributed Systems Architect, DevOps Architect, AI Systems Architect, and Technical Lead** for this project.

Your responsibility in this phase is to establish the complete technical architecture for **RepoScore**.

You are NOT implementing the product yet.

You are creating the architectural contract that every future phase must follow.

The architecture must be:

- technically coherent
- secure
- modular
- testable
- observable
- reproducible
- free-first
- extensible
- maintainable
- suitable for autonomous AI-assisted development

Do not optimize for speed. Optimize for correctness and architectural integrity.

---

# 1. PROJECT DEFINITION

## 1.1 Product

**RepoScore**

An autonomous repository intelligence and software evaluation platform.

The platform accepts a GitHub repository and evaluates it using:

1. Repository intelligence
2. Static analysis
3. Dependency analysis
4. Security analysis
5. Secure sandboxed execution
6. Build verification
7. Runtime testing
8. Behavioral evaluation
9. Resource observation
10. Evidence collection
11. Deterministic scoring
12. AI-assisted reasoning
13. Human-readable reporting

The fundamental principle is:

> **Do not merely analyze what the code looks like. Determine what the software actually does.**

---

# 2. CORE PRODUCT FLOW

The canonical system flow is:

```text
GitHub Repository
       │
       ▼
Repository Ingestion
       │
       ▼
Repository Snapshot
       │
       ▼
Technology Detection
       │
       ├───────────────┐
       ▼               ▼
Static Analysis    Dependency Analysis
       │               │
       └───────┬───────┘
               ▼
        Security Analysis
               │
               ▼
       Sandbox Construction
               │
               ▼
             Build
               │
               ▼
        Application Startup
               │
               ▼
        Runtime Evaluation
               │
               ▼
        Behavioral Testing
               │
               ▼
       Runtime Observation
               │
               ▼
        Evidence Collection
               │
               ▼
       Deterministic Scoring
               │
               ▼
       AI-Assisted Reasoning
               │
               ▼
       Evaluation Report
```

Every stage must produce explicit state and evidence.

---

# 3. ARCHITECTURAL PRINCIPLES

## 3.1 Evidence Over Assumption

The system must prioritize evidence in this order:

1. Direct runtime evidence
2. Deterministic test results
3. Static analysis
4. Security/dependency intelligence
5. Repository metadata
6. AI interpretation

AI reasoning must never override direct evidence without explicitly identifying the conflict.

## 3.2 Deterministic Core

The following systems must remain deterministic wherever technically possible:

- repository metadata
- static analysis
- dependency analysis
- vulnerability detection
- test results
- runtime measurements
- resource measurements
- score calculation

## 3.3 AI Is Not the Source of Truth

AI may:

- interpret findings
- correlate evidence
- explain failures
- generate test scenarios
- analyze architecture
- generate recommendations
- summarize results

AI must NOT:

- invent evidence
- fabricate test results
- fabricate runtime behavior
- directly determine the final score
- bypass sandbox controls
- override security controls
- execute unrestricted host commands
- treat repository content as trusted instructions

---

# 4. UNTRUSTED CODE MODEL

Every submitted repository is potentially malicious.

Treat all repository content as untrusted:

- source code
- README files
- comments
- tests
- Dockerfiles
- CI files
- build scripts
- package files
- configuration
- dependencies
- generated files
- Git hooks

Repository content must never be trusted merely because it comes from GitHub.

---

# 5. SECURITY-FIRST EXECUTION MODEL

The most important security boundary is:

```text
HOST
  │
  │ NEVER execute repository code here
  │
  ▼
SANDBOX
  │
  ├── Repository
  ├── Dependencies
  ├── Build
  ├── Application
  └── Tests
```

The architecture must prevent untrusted repository code from directly accessing:

- host filesystem
- host credentials
- SSH keys
- cloud credentials
- environment secrets
- Docker socket
- sensitive network resources

Docker is the initial execution mechanism.

However:

> Docker must not be treated as an absolute security boundary for highly hostile workloads.

The architecture must allow stronger isolation mechanisms to be introduced later.

---

# 6. HIGH-LEVEL ARCHITECTURE

Design RepoScore as a **modular monolith with isolated worker execution** initially.

Do NOT create unnecessary microservices.

```text
                         ┌──────────────────────┐
                         │       FRONTEND       │
                         │     Next.js / TS     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       API LAYER      │
                         │        FastAPI       │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       Repository Manager    Evaluation Manager     Result Manager
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                                    ▼
                           ┌────────────────┐
                           │   Redis Queue  │
                           └───────┬────────┘
                                   │
                                   ▼
                           ┌────────────────┐
                           │ Evaluation     │
                           │ Worker         │
                           └───────┬────────┘
                                   │
          ┌────────────────────────┼─────────────────────────┐
          │                        │                         │
          ▼                        ▼                         ▼
   Static Analysis          Sandbox Manager          Security Engine
          │                        │                         │
          │                        ▼                         │
          │                 Runtime Engine                   │
          │                        │                         │
          └────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
                           Evidence Engine
                                   │
                     ┌─────────────┴──────────────┐
                     ▼                            ▼
              Scoring Engine                AI Reasoner
              Deterministic                Evidence-Based
                     │                            │
                     └─────────────┬──────────────┘
                                   ▼
                           Evaluation Report
```

---

# 7. COMPONENT RESPONSIBILITIES

## 7.1 Frontend

Technology:

- Next.js
- TypeScript

Responsibilities:

- repository submission
- evaluation creation
- evaluation progress
- score visualization
- dimension breakdown
- findings
- runtime evidence
- security findings
- recommendations
- evaluation history
- comparison

The frontend must never contain core evaluation logic.

---

# 8. API LAYER

Technology:

- FastAPI
- Pydantic

Responsibilities:

- input validation
- authentication boundary
- authorization
- repository submission
- evaluation creation
- evaluation status
- result retrieval
- cancellation
- pagination
- rate limiting
- health checks

The API layer must never directly execute arbitrary repository code.

---

# 9. REPOSITORY MANAGER

Responsibilities:

- validate repository URL
- communicate with GitHub
- retrieve metadata
- clone repository
- identify commit SHA
- identify branch/tag
- create immutable repository snapshot
- detect languages
- detect package managers
- detect frameworks
- detect build systems
- detect test frameworks
- identify potential entry points

Repository ingestion must remain separate from execution.

---

# 10. EVALUATION ORCHESTRATOR

The Evaluation Orchestrator owns the evaluation lifecycle.

Minimum states:

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

State transitions must be explicit.

No implicit state changes.

No hidden failure states.

---

# 11. WORKER ARCHITECTURE

Workers execute long-running evaluation operations.

Workers must:

- receive jobs
- execute defined steps
- report state
- enforce timeouts
- capture failures
- emit structured events
- clean up resources
- never trust repository instructions

Workers must be restartable.

Evaluation state must survive worker failure.

---

# 12. SANDBOX MANAGER

The Sandbox Manager owns all untrusted execution.

Responsibilities:

- create execution environment
- configure CPU limits
- configure memory limits
- configure process limits
- configure filesystem isolation
- configure network policy
- enforce execution timeout
- run as non-root
- restrict capabilities
- capture stdout
- capture stderr
- collect resource metrics
- terminate execution
- cleanup

The sandbox must be independently testable.

---

# 13. RUNTIME ENGINE

The Runtime Engine determines what software actually does.

Responsibilities:

- determine execution strategy
- build application
- start application
- detect startup failures
- execute tests
- execute generated scenarios
- interact with APIs where applicable
- observe runtime behavior
- capture errors
- capture latency
- capture resource consumption
- detect crashes
- classify runtime failures

Do not assume every repository is an HTTP API.

Architecture must support evaluator types:

```text
Evaluator
├── Python Application
├── Node Application
├── Java Application
├── REST API
├── CLI
├── Library
└── Unsupported
```

The evaluator framework must be extensible.

---

# 14. STATIC ANALYSIS ENGINE

Create a common analyzer abstraction.

```text
Analyzer
├── Language Analyzer
├── Security Analyzer
├── Complexity Analyzer
├── Dependency Analyzer
├── Test Analyzer
└── Architecture Analyzer
```

Tools must be adapters behind this interface.

Potential tools include:

- Tree-sitter
- Semgrep
- Ruff
- Bandit
- mypy
- ESLint
- language-specific analyzers

Do not hard-code RepoScore around one tool.

---

# 15. SECURITY ENGINE

The Security Engine evaluates:

- vulnerable dependencies
- dangerous code patterns
- secrets exposure indicators
- insecure configuration
- dependency risks
- known vulnerabilities
- sandbox violations
- runtime security events

Use free/open-source sources wherever possible.

Potential source:

- OSV

Potential tools:

- Semgrep
- Trivy
- language-specific security tools

Security findings must become structured evidence.

---

# 16. EVIDENCE ENGINE

The Evidence Engine is a central architectural component.

Every finding must be normalized into structured evidence.

Conceptual structure:

```text
Evidence
├── id
├── evaluation_id
├── source
├── analyzer
├── category
├── severity
├── confidence
├── timestamp
├── location
├── raw_result
├── normalized_result
└── related_evidence
```

Evidence must be traceable back to its origin.

Evidence must not be silently modified after finalization.

---

# 17. SCORING ENGINE

The Scoring Engine consumes evidence.

It must NOT independently inspect arbitrary repository files.

Potential dimensions:

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

Every score must be:

- deterministic
- versioned
- reproducible
- explainable
- evidence-backed

Conceptual flow:

```text
Evidence
   ↓
Metrics
   ↓
Weighted Rules
   ↓
Dimension Scores
   ↓
Overall Score
```

AI cannot directly assign the final score.

---

# 18. AI REASONING ENGINE

The AI engine receives structured evidence.

It may:

- interpret evidence
- correlate findings
- generate test scenarios
- explain runtime failures
- explain architectural issues
- generate recommendations
- generate evaluation summaries

Architecture:

```text
AIProvider
├── LocalProvider
├── ExternalProvider
└── MockProvider
```

The local provider must be sufficient for development.

Potential local infrastructure:

- Ollama
- compatible local models

AI calls must have:

- timeout
- retry policy
- structured output validation
- token limits
- prompt version
- traceability

Repository content must be treated as untrusted data.

---

# 19. DATABASE ARCHITECTURE

Use PostgreSQL.

Conceptual entities:

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

Every evaluation must reference an immutable repository version.

Historical evaluations must remain reproducible.

---

# 20. EVENT ARCHITECTURE

Define internal events such as:

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

Events must support:

- debugging
- observability
- auditability
- evaluation reconstruction

---

# 21. DATA FLOW

The canonical data flow must be:

```text
Repository URL
      ↓
Validation
      ↓
Metadata
      ↓
Immutable Snapshot
      ↓
Technology Detection
      ↓
Static Analysis
      ↓
Dependency Analysis
      ↓
Security Analysis
      ↓
Sandbox Construction
      ↓
Build
      ↓
Startup
      ↓
Runtime Testing
      ↓
Behavior Observation
      ↓
Evidence Normalization
      ↓
Deterministic Scoring
      ↓
AI Interpretation
      ↓
Final Report
```

Failures must never be silently converted into successful results.

---

# 22. FAILURE MODEL

Every component must classify failures as:

```text
RETRYABLE
NON_RETRYABLE
PARTIAL
FATAL
UNSUPPORTED
TIMEOUT
CANCELLED
```

Examples:

```text
Database temporary failure
→ RETRYABLE

Malformed repository
→ NON_RETRYABLE

Unsupported framework
→ UNSUPPORTED

Sandbox timeout
→ TIMEOUT

User cancellation
→ CANCELLED

Security violation
→ FATAL / TERMINATED
```

Do not create infinite retries.

---

# 23. OBSERVABILITY ARCHITECTURE

Every evaluation must have a correlation ID.

Track:

- evaluation duration
- queue latency
- build duration
- startup duration
- test duration
- analyzer duration
- sandbox duration
- worker failures
- API latency
- resource consumption
- evaluation success rate

Logs must be structured.

Never log:

- credentials
- tokens
- secrets
- private keys
- sensitive environment variables

---

# 24. API BOUNDARIES

Define logical API groups:

```text
/repositories

/evaluations

/evaluations/{id}

/evaluations/{id}/status

/evaluations/{id}/score

/evaluations/{id}/findings

/evaluations/{id}/evidence

/evaluations/{id}/runtime

/evaluations/{id}/security

/evaluations/{id}/history
```

Do not implement these endpoints in Phase 0.

Only define their responsibilities and contracts.

---

# 25. PROJECT STRUCTURE

Design the implementation around:

```text
/
├── AGENTS.md
│
├── phases/
│   ├── 00_ARCHITECTURE.md
│   ├── 01_REQUIREMENTS.md
│   ├── 02_SECURITY.md
│   └── ...
│
├── docs/
│   ├── requirements/
│   ├── architecture/
│   ├── security/
│   ├── api/
│   ├── scoring/
│   └── phase-reports/
│
├── backend/
│   ├── api/
│   ├── core/
│   ├── repository/
│   ├── orchestration/
│   ├── workers/
│   ├── sandbox/
│   ├── analyzers/
│   ├── runtime/
│   ├── security/
│   ├── evidence/
│   ├── scoring/
│   ├── ai/
│   ├── database/
│   └── observability/
│
├── frontend/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── e2e/
│   └── fixtures/
│
└── infrastructure/
    ├── docker/
    └── ci/
```

This is an architectural target, not an instruction to create all directories during Phase 0.

---

# 26. EXTERNAL DEPENDENCY POLICY

For every planned dependency document:

- purpose
- license
- cost
- security implications
- failure behavior
- replacement strategy

Categorize dependencies:

```text
REQUIRED
OPTIONAL
DEVELOPMENT_ONLY
REPLACEABLE
```

No core component may become unnecessarily dependent on a proprietary paid service.

---

# 27. FREE-FIRST TECHNOLOGY STRATEGY

Preferred stack:

```text
Backend:
Python
FastAPI
Pydantic

Database:
PostgreSQL
SQLAlchemy
Alembic

Queue:
Redis

Sandbox:
Docker

Repository:
Git
GitHub API

Static Analysis:
Tree-sitter
Semgrep
Ruff
Bandit
mypy
ESLint
other open-source analyzers

Security:
OSV
Trivy
open-source analyzers

Testing:
Pytest

AI:
Ollama / local models

Frontend:
Next.js
TypeScript

CI/CD:
GitHub Actions
```

This is a preferred architecture, not permission to blindly add every listed tool.

Only introduce a dependency when it provides measurable value.

---

# 28. ARCHITECTURAL DECISION RECORDS

Create ADRs for:

```text
ADR-001 — Modular Monolith Architecture
ADR-002 — Docker Sandbox Architecture
ADR-003 — Evidence-First Evaluation
ADR-004 — Deterministic Scoring
ADR-005 — Local-First AI
ADR-006 — PostgreSQL Persistence
ADR-007 — Redis Job Queue
ADR-008 — Analyzer Adapter Architecture
ADR-009 — Runtime Evaluator Architecture
ADR-010 — Immutable Repository Snapshots
```

Each ADR must contain:

```text
Context
Decision
Alternatives
Consequences
Security Impact
Operational Impact
```

---

# 29. REQUIRED DOCUMENTATION

Create:

```text
docs/architecture/

SYSTEM_ARCHITECTURE.md
COMPONENT_ARCHITECTURE.md
DATA_FLOW.md
EVALUATION_LIFECYCLE.md
SANDBOX_ARCHITECTURE.md
ANALYZER_ARCHITECTURE.md
RUNTIME_ARCHITECTURE.md
EVIDENCE_ARCHITECTURE.md
SCORING_ARCHITECTURE.md
AI_ARCHITECTURE.md
OBSERVABILITY_ARCHITECTURE.md
FAILURE_MODEL.md
DEPENDENCY_STRATEGY.md
```

Create:

```text
docs/architecture/adrs/
```

and place all ADRs there.

Use Mermaid diagrams wherever they improve clarity.

---

# 30. ARCHITECTURAL SELF-REVIEW

Before completing this phase, perform an independent review of your own architecture.

Act as a hostile senior architect.

Look specifically for:

- circular dependencies
- unclear ownership
- excessive coupling
- unnecessary microservices
- security boundary violations
- unsafe sandbox assumptions
- AI overreach
- nondeterministic scoring
- missing failure states
- missing observability
- data consistency problems
- concurrency risks
- reproducibility problems
- scalability problems
- unsupported repository types
- hidden paid dependencies
- unnecessary dependencies
- architectural contradictions

If a problem is identified:

1. Document it.
2. Resolve it.
3. Update affected architecture.
4. Update the relevant ADR.

Do not knowingly leave architectural contradictions unresolved.

---

# 31. PHASE 0 PROHIBITIONS

Do NOT:

- implement API endpoints
- implement database migrations
- implement workers
- implement sandbox execution
- implement scoring
- implement static analyzers
- implement runtime evaluators
- implement AI calls
- implement frontend pages
- install unnecessary runtime dependencies
- create fake functionality
- create placeholder production logic

Phase 0 is documentation and architecture.

---

# 32. ACCEPTANCE CRITERIA

Phase 0 passes only when:

- [ ] Product definition is documented.
- [ ] System architecture exists.
- [ ] Component architecture exists.
- [ ] Evaluation lifecycle exists.
- [ ] Data flow exists.
- [ ] Security boundaries are defined.
- [ ] Sandbox architecture exists.
- [ ] Runtime architecture exists.
- [ ] Static-analysis architecture exists.
- [ ] Evidence architecture exists.
- [ ] Scoring architecture exists.
- [ ] AI architecture exists.
- [ ] Database model is defined.
- [ ] API boundaries are defined.
- [ ] Event architecture exists.
- [ ] Failure model exists.
- [ ] Observability architecture exists.
- [ ] Free-first dependency strategy exists.
- [ ] Project structure is defined.
- [ ] ADRs are created.
- [ ] Architecture has been self-reviewed.
- [ ] No production implementation has been introduced.
- [ ] No secrets have been introduced.

---

# 33. PHASE REPORT

Create:

```text
docs/phase-reports/PHASE_00.md
```

Include:

```text
# Phase 00 Report

## Status

PASS / FAIL

## Objective

## Architecture Summary

## Documents Created

## ADRs Created

## Major Decisions

## Security Decisions

## Known Risks

## Future Phase Dependencies

## Self-Review Results

## Acceptance Criteria

## Commit
```

---

# 34. GIT COMMIT GATE

Before committing:

1. Run `git status`.
2. Review the complete diff.
3. Confirm this phase contains architecture documentation only.
4. Confirm no secrets exist.
5. Confirm no accidental implementation exists.
6. Confirm all required documents exist.
7. Confirm ADRs are complete.
8. Confirm diagrams are present.
9. Confirm Phase 0 acceptance criteria.
10. Confirm the working tree is clean after commit.

Commit exactly as:

```text
phase(00): establish system architecture
```

Record the resulting commit SHA in:

```text
docs/phase-reports/PHASE_00.md
```

---

# 35. FINAL RULE

The architecture created in this phase becomes the **architectural contract for the entire project**.

Every future phase MUST:

1. Read this phase.
2. Read the architecture documents.
3. Verify the current repository against the architecture.
4. Preserve existing architectural decisions.
5. Run regression checks.
6. Document any required architectural change through an ADR.

A future phase may NOT silently redesign the system.

If a future requirement requires architectural change:

```text
Identify conflict
      ↓
Document reason
      ↓
Create/update ADR
      ↓
Update architecture
      ↓
Review impact on previous phases
      ↓
Implement change
      ↓
Run complete regression
```

Never sacrifice architectural integrity for implementation speed.

**Phase 00 is complete only when the system has a coherent, secure, evidence-driven, free-first architecture that another engineering team could implement without making fundamental architectural decisions themselves.**
