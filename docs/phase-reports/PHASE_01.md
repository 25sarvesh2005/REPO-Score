# Phase 01 Report — Requirements Engineering

> **Phase:** 01  
> **Phase Name:** Requirements Engineering  
> **Status:** PASS  
> **Target System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Governance Authority:** `phases/01_REQUIREMENTS.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Executive Summary

Phase 01 has completed the transformation of the technical architecture established in Phase 00 into a comprehensive, testable, and traceable Software Requirements Specification (SRS) for **RepoScore**.

In strict accordance with the Prime Directives:
- **No production code** was implemented.
- **Evidence Over Assumption** is encoded into every evaluation and scoring requirement.
- **Deterministic Core** scoring formulas, weights, and rules were established with zero AI influence.
- **Hostile Code Threat Model** is fully formalized with strict host-versus-sandbox boundaries.
- **AI Role Boundaries** are rigidly bounded with prompt injection defense, structured Pydantic schemas, and local Ollama defaults.
- **Free-First Ecosystem** dependencies were preserved with zero mandatory paid cloud services.

---

## 2. Start State & Pre-Phase Audit

- **Initial Git Commit:** `059b5cd` (`phase(00): establish system architecture`)
- **Phase 00 Report Reviewed:** [`PHASE_00.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/phase-reports/PHASE_00.md) (Status: **PASS**)
- **ADRs Audited:** ADR-001 through ADR-010 confirmed intact.
- **Regression Check:** Verified modular monolith architecture, Docker sandbox boundary, PostgreSQL relational model, Redis job queues, evidence model, and local-first AI.
- **Git Tree Cleanup:** Cleaned redundant duplicate `plan/00_ARCHITECTURE.md` in favor of official `phases/00_ARCHITECTURE.md`.

---

## 3. Deliverables Created & Modified

### Deliverables Created:
1. [`docs/requirements/SRS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/SRS.md) — Master Software Requirements Specification.
2. [`docs/requirements/FUNCTIONAL_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/FUNCTIONAL_REQUIREMENTS.md) — 45 functional requirements covering ingestion, detection, orchestration, and reporting.
3. [`docs/requirements/NON_FUNCTIONAL_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/NON_FUNCTIONAL_REQUIREMENTS.md) — 26 non-functional requirements covering security, reliability, determinism, performance, and maintainability.
4. [`docs/requirements/SECURITY_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/SECURITY_REQUIREMENTS.md) — 20 security requirements detailing sandbox confinement, cgroups quotas, secret redaction, and prompt injection defenses.
5. [`docs/requirements/API_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/API_REQUIREMENTS.md) — 22 API interface requirements covering endpoints, SSE streaming, RFC 7807 error envelopes, and correlation headers.
6. [`docs/requirements/EVALUATION_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/EVALUATION_REQUIREMENTS.md) — 40 evaluation requirements covering the 17-state FSM, static analyzers, build/startup probes, runtime telemetry, and evidence normalization.
7. [`docs/requirements/SCORING_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/SCORING_REQUIREMENTS.md) — 24 deterministic scoring requirements covering the 10 evaluation dimensions, mathematical clamping formulas, severity multipliers, and itemized receipts.
8. [`docs/requirements/AI_REQUIREMENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/AI_REQUIREMENTS.md) — 20 AI requirements establishing the `IAIProvider` protocol, local Ollama default, Pydantic structured output validation, and prompt injection defense.
9. [`docs/requirements/MVP_SCOPE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/MVP_SCOPE.md) — Explicit MVP vertical slice definition focusing on Python and Node.js Web APIs and CLI tools.
10. [`docs/requirements/OUT_OF_SCOPE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/OUT_OF_SCOPE.md) — Explicit boundary declarations forbidding host execution, cloud deployments, and billing in early phases.
11. [`docs/requirements/TRACEABILITY_MATRIX.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/requirements/TRACEABILITY_MATRIX.md) — Complete bidirectional mapping of requirements to components, phases (02–17), tests, and evidence artifacts.
12. [`docs/phase-reports/PHASE_01.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/phase-reports/PHASE_01.md) — This Phase 01 Report.

### Files Modified:
- Redundant `plan/00_ARCHITECTURE.md` tracked file staged for removal.
- `phases/01_REQUIREMENTS.md` tracked in repository.

---

## 4. Requirements Metrics & Distribution

### 4.1 Count by Domain
- **Functional Requirements (`FR-xxx`):** 45
- **Non-Functional Requirements (`NFR-xxx`):** 26
- **Security Requirements (`SEC-xxx`):** 20
- **API Requirements (`API-xxx`):** 22
- **Evaluation Requirements (`EVAL-xxx`):** 40
- **Scoring Requirements (`SCORE-xxx`):** 24
- **AI Requirements (`AI-xxx`):** 20
- **Total Requirements Defined:** **197**

### 4.2 Count by Priority
- **P0 (Mandatory Core / Security / MVP):** 122
- **P1 (MVP Quality & Robustness):** 58
- **P2 (Post-MVP Enhancements):** 17
- **P3 (Future Architecture Goals):** 0
- **Total:** **197**

### 4.3 Open Questions & Unbenchmarked Items
- **Total Tracked TBD Items:** 4
  1. Maximum uncompressed repository size threshold (`TBD — requires benchmarking`, default 250MB).
  2. Concurrent sandbox container density per worker host (`TBD — requires benchmarking`, target 4).
  3. Package caching proxy overhead latency (`TBD — requires benchmarking`, target < 15%).
  4. Local Ollama LLM token generation rate (`TBD — requires benchmarking`, target < 20s).

---

## 5. Architectural Integrity & Regression Check

A comparative audit of Phase 01 specifications against `/phases/00_ARCHITECTURE.md` and `/docs/architecture/*` confirmed **ZERO ARCHITECTURAL DRIFT**:
- [x] AI has NOT been granted authoritative scoring powers.
- [x] Untrusted code execution is strictly restricted to isolated Docker sandboxes.
- [x] Snapshot immutability is strictly enforced.
- [x] Scoring remains 100% deterministic, rule-based, and evidence-backed.
- [x] Free-first local tooling (Ollama, PostgreSQL, Redis, Docker, OSV) remains standard.
- [x] No proprietary cloud dependencies were introduced.

---

## 6. Acceptance Criteria Checklist

- [x] Phase 00 was audited and verified (commit `059b5cd`).
- [x] Redundant duplicate files cleaned up.
- [x] Master SRS document created (`docs/requirements/SRS.md`).
- [x] Functional requirements document created (`docs/requirements/FUNCTIONAL_REQUIREMENTS.md`).
- [x] Non-functional requirements document created (`docs/requirements/NON_FUNCTIONAL_REQUIREMENTS.md`).
- [x] Security requirements document created (`docs/requirements/SECURITY_REQUIREMENTS.md`).
- [x] API requirements document created (`docs/requirements/API_REQUIREMENTS.md`).
- [x] Evaluation requirements document created (`docs/requirements/EVALUATION_REQUIREMENTS.md`).
- [x] Scoring requirements document created (`docs/requirements/SCORING_REQUIREMENTS.md`).
- [x] AI requirements document created (`docs/requirements/AI_REQUIREMENTS.md`).
- [x] MVP scope document created (`docs/requirements/MVP_SCOPE.md`).
- [x] Out-of-scope document created (`docs/requirements/OUT_OF_SCOPE.md`).
- [x] Traceability matrix created (`docs/requirements/TRACEABILITY_MATRIX.md`).
- [x] Requirement IDs are unique and stable (`FR-xxx`, `NFR-xxx`, `SEC-xxx`, `API-xxx`, `EVAL-xxx`, `SCORE-xxx`, `AI-xxx`).
- [x] Critical P0 requirements have formal Gherkin acceptance criteria (`Given/When/Then`).
- [x] Unbenchmarked metrics use `TBD — requires benchmarking` without fake precision.
- [x] Zero production implementation code was introduced.
- [x] Phase report created (`docs/phase-reports/PHASE_01.md`).
- [x] Repository ready for Git commit gate.

---

## 7. Commit Information

- **Required Commit Message:** `phase(01): establish software requirements`
- **Commit SHA:** `PENDING_COMMIT` *(Will be populated immediately post-commit)*

---

## 8. Handoff to Phase 02

**Next Phase:** Phase 02 — Security & Threat Modeling (Sandbox Security Specification).

Phase 02 must:
1. Review [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md), Phase 00 architecture, Phase 01 requirements, and Phase 01 report.
2. Formulate the comprehensive Threat Model across all attack surfaces (malicious code, prompt injection, supply chain attacks, resource exhaustion).
3. Specify exact container cgroups v2 parameters, Linux capability drops, seccomp profiles, and network proxy rules without weakening any Phase 01 security requirement.
