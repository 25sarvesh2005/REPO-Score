# ADR-004: Deterministic Scoring

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Core Architecture & Product Team  
> **Consulted:** Technical Leads  

---

## Context
A major failure mode of AI-driven developer tooling is non-determinism: analyzing the same repository twice produces conflicting scores (e.g., 78/100 on run 1, and 85/100 on run 2). Software engineers, security officers, and CI/CD quality gates require reproducible, mathematical consistency to trust an evaluation platform.

---

## Decision
We enforce a **strictly deterministic, rule-based Scoring Engine**:
- The Scoring Engine operates on pure mathematical algorithms consuming structured `EvidenceRecord` inputs.
- AI models are strictly barred from participating in numerical score calculations or weight adjustments.
- Given the exact same evidence records and scoring version (e.g. `1.0.0`), the system is guaranteed to compute the exact same dimension scores and overall composite score.
- The scoring model is organized into 10 explicit dimensions with transparent weighting formulas, bounded deductions, and explainable itemized receipts.

---

## Alternatives Considered
1. **LLM-Based Subjective Grading**:
   - Asking the model: *"Rate this codebase from 1 to 100 based on the findings."*
   - *Rejected*: Inconsistent, susceptible to prompt injection, impossible to use in automated CI quality gates.
2. **Hybrid Probabilistic Scoring**:
   - Using statistical heuristics and probabilistic bayesian weights.
   - *Rejected*: Lacks transparency and complicates user remediation workflows.

---

## Consequences
- **Positive**:
  - Deterministic CI quality gates: Repositories can reliably assert `score >= 80` in automated deployment pipelines.
  - Fair and unbiased: Evaluates every project under identical, transparent mathematical criteria.
  - Clear user path to improvement: Every deducted point maps directly to a tangible remediation action.
- **Negative**:
  - Requires thoughtful ongoing calibration of severity penalty multipliers and dimension weights.

---

## Security Impact
- Eliminates prompt injection vectors aimed at inflating scores or bypassing security gates.

---

## Operational Impact
- Sub-millisecond scoring execution time, drastically reducing CPU overhead and eliminating API costs associated with grading.
