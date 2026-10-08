# ADR-003: Evidence-First Evaluation

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Core Architecture & Scoring Team  
> **Consulted:** Systems & Security Architects  

---

## Context
Traditional repository review tools frequently make broad assertions without providing concrete, traceable proof (e.g. stating "Code quality is low" without line references, or computing an opaque aggregate score). Furthermore, when LLMs are integrated into evaluation pipelines, they tend to hallucinate issues or exaggerate minor infractions.

We require an architectural guarantee that every evaluation judgment is backed by empirical data and verifiable facts.

---

## Decision
We adopt an **Evidence-First Architecture**:
- All analyzers, test runners, runtime monitors, and security tools must normalize findings into canonical `EvidenceRecord` database entities before any scoring or AI interpretation occurs.
- An evidence record includes immutable identifiers, source attribution, category, severity, confidence rating, exact code location (file, start/end lines), raw tool output, and normalized metadata.
- Downstream Scoring Engines and AI Reasoners are **strictly consumers of evidence**. They cannot inspect the filesystem directly to invent new findings.
- Every score deduction, score bonus, and AI narrative claim must cite specific `evidence.id` records.

---

## Alternatives Considered
1. **Direct Analyzer-to-Score Pipeline**:
   - Analyzers output raw scores directly (e.g., Semgrep emits 80/100, Pytest emits 90/100).
   - *Rejected*: Inflexible, impossible to audit, obscures underlying issues, cannot be synthesized by an AI reasoning layer.
2. **AI-Direct Analysis (Feeding Raw Code Directly to LLMs)**:
   - *Rejected*: Severe hallucinations, non-reproducible scoring, high token cost, vulnerability to prompt injection attacks.

---

## Consequences
- **Positive**:
  - Absolute auditability: Users can inspect the exact evidence behind every score deduction.
  - Decoupled pipeline: Analyzers focus strictly on detecting facts; the scoring engine focuses strictly on evaluating their weight.
  - Resilience: Even if the AI reasoning layer fails, 100% of the structured evidence remains available to the user.
- **Negative**:
  - Requires maintaining normalization adapters for all integrated static and runtime tools.

---

## Security Impact
- Prevents malicious repositories from deceiving the evaluation engine via deceptive comments or cosmetic layout.
- Provides cryptographic/tamper-evident evidence tracking.

---

## Operational Impact
- Increased database writes to the `evidence` table, mitigated by PostgreSQL bulk inserts, partitioning, and compound indexing.
