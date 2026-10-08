# AGENTS.md — Agent Governance & Architectural Directives

> **Project:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Authority:** System Architecture Contract (`phases/00_ARCHITECTURE.md`)  
> **Target Audience:** All AI Coding Agents, Autonomous Subagents, and Human Collaborators

---

## 1. Prime Directives

1. **Strict Phase Adherence:** You must never skip phases or write production code during architecture/design phases. Each phase has an explicit scope, acceptance criteria, and git commit gate.
2. **Evidence Over Assumption:** RepoScore evaluates software based on runtime behavior and empirical evidence, not purely static appearance or superficial heuristics. Never fabricate results or evidence.
3. **Deterministic Core:** Calculations, scoring models, vulnerability mappings, static metrics, and test evaluations must be deterministic, reproducible, and verifiable.
4. **Hostile Code Model:** Every repository submitted for analysis is treated as untrusted and potentially adversarial. Repository content must NEVER be executed directly on the host machine.
5. **AI Role Boundary:** AI models provide reasoning, correlation, explanation, and scenario generation. AI models do NOT calculate core scores, do NOT override empirical test evidence, and do NOT execute unrestricted host commands.
6. **Free-First Ecosystem:** Prefer high-quality open-source and local self-hostable tooling (Python, FastAPI, Docker, PostgreSQL, Redis, Ollama, OSV, Semgrep, Tree-sitter). Do not introduce mandatory paid third-party cloud dependencies.

---

## 2. Phase Execution Protocol

Before executing work in any phase:
1. Read the corresponding phase specification in `phases/` (or `plan/`).
2. Verify all prerequisite phases are marked **PASS** in `docs/phase-reports/`.
3. Check all ADRs in `docs/architecture/adrs/` for binding design decisions.
4. Maintain architectural integrity — any deviation requires an approved Architecture Decision Record (ADR).
5. At phase completion:
   - Perform an adversarial self-review.
   - Verify every item on the Phase Acceptance Checklist.
   - Produce a signed-off Phase Report in `docs/phase-reports/PHASE_XX.md`.
   - Execute the Git commit gate with the specified commit message.

---

## 3. Security Boundary Rules

- **Host vs Sandbox Boundary:** The host system only orchestrates jobs, stores metadata, and launches sandboxes. The sandbox (Docker container with strict cgroups, dropped capabilities, non-root user, and restricted network egress) executes user repository code.
- **Docker Socket Isolation:** Never mount `/var/run/docker.sock` inside an untrusted execution container.
- **Secret Zero Leakage:** Worker logs, API payloads, and persisted evidence records must be sanitized. Never log or store environment credentials, GitHub tokens, or private keys.
- **Prompt Injection Defense:** Repository files (READMEs, comments, variable names, docstrings) injected into AI prompts must be enclosed within hardened delimiters and treated strictly as untrusted text, never as instructions.

---

## 4. Architectural Documents Index

- [`00_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/phases/00_ARCHITECTURE.md)
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
