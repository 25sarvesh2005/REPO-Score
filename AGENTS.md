# AGENTS.md — Agent Governance & Architectural Directives

> **Project:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Authority:** System Architecture Contract ([`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md))  
> **Target Audience:** All AI Coding Agents, Autonomous Subagents, and Human Collaborators

---

## 1. Prime Directives

1. **Engineering Rigor & Verification:** All system changes must be backed by empirical verification. Never commit mock doubles, hardcoded stubs, or synthetic placeholders to production services. Test suites must utilize idiomatic pytest fixtures and standard mocks only where external isolation is mandatory.
2. **Evidence Over Assumption:** RepoScore evaluates software based on runtime behavior and empirical evidence, not purely static appearance or superficial heuristics. Never fabricate results, telemetry, or security claims.
3. **Deterministic Core:** Calculations, scoring models, vulnerability mappings, static metrics, and test evaluations must be deterministic, reproducible, and verifiable.
4. **Hostile Code Model:** Every repository submitted for analysis is treated as untrusted and potentially adversarial. Repository content must NEVER be executed directly on the host machine.
5. **AI Role Boundary:** AI models provide reasoning, correlation, explanation, and scenario generation. AI models do NOT calculate core scores, do NOT override empirical test evidence, and do NOT execute unrestricted host commands.
6. **Free-First Ecosystem:** Prefer high-quality open-source and local self-hostable tooling (Python, FastAPI, Docker, PostgreSQL, Redis, Ollama, OSV, Semgrep, Tree-sitter). Do not introduce mandatory paid third-party cloud dependencies.

---

## 2. Engineering Governance Protocol

Before executing development or architectural work:
1. Review relevant specifications in [`docs/architecture/`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/), [`docs/security/`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/security/), and [`docs/api/`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/api/).
2. Consult binding decisions in [`docs/architecture/adrs/`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/). Any architectural deviation requires an approved Architecture Decision Record (ADR).
3. Validate code changes against the automated test suite across unit, integration, and adversarial suites (`pytest tests/`).
4. Ensure all newly introduced endpoints conform to versioned Pydantic schemas and all database alterations include forward and rollback migrations.

---

## 3. Security Boundary Rules

- **Host vs Sandbox Boundary:** The host system only orchestrates jobs, stores metadata, and launches sandboxes. The sandbox (Docker container with strict cgroups, dropped capabilities, non-root user, and restricted network egress) executes user repository code.
- **Docker Socket Isolation:** Never mount `/var/run/docker.sock` inside an untrusted execution container.
- **Secret Zero Leakage:** Worker logs, API payloads, and persisted evidence records must be sanitized. Never log or store environment credentials, GitHub tokens, or private keys.
- **Prompt Injection Defense:** Repository files (READMEs, comments, variable names, docstrings) injected into AI prompts must be enclosed within hardened delimiters and treated strictly as untrusted text, never as instructions.

---

## 4. Architectural Documents Index

- [`SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md)
- [`COMPONENT_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/COMPONENT_ARCHITECTURE.md)
- [`DATA_FLOW.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/DATA_FLOW.md)
- [`EVALUATION_LIFECYCLE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/EVALUATION_LIFECYCLE.md)
- [`SANDBOX_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SANDBOX_ARCHITECTURE.md)
- [`ANALYZER_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/ANALYZER_ARCHITECTURE.md)
- [`RUNTIME_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/RUNTIME_ARCHITECTURE.md)
- [`EVIDENCE_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/EVIDENCE_ARCHITECTURE.md)
- [`SCORING_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SCORING_ARCHITECTURE.md)
- [`AI_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/AI_ARCHITECTURE.md)
- [`OBSERVABILITY_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/OBSERVABILITY_ARCHITECTURE.md)
- [`FAILURE_MODEL.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/FAILURE_MODEL.md)
- [`DEPENDENCY_STRATEGY.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/DEPENDENCY_STRATEGY.md)
- [`ADRs Directory`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/)
