# ADR-011: Strict Quality Gates & Fatal Flaw Guardrails

> **Status:** Superseded / Refined  
> **Date:** 2026-10-13  
> **Deciders:** Core Architecture & Scoring Team  
> **Superseded By:** ADR-003: Pure Evidence-First Evaluation  
> **Preceding ADRs:** ADR-003, ADR-004  

---

## 1. Context

In raw weighted composite scoring, high performance in isolated dimensions can mask catastrophic failures in other critical areas. For example, a repository containing severe Remote Code Execution (RCE) CVEs and plaintext hardcoded AWS root keys could previously achieve an overall score of `84.0` (Grade B) or higher if non-security dimensions scored well.

Real-world engineering leaders, CISOs, and enterprise compliance auditors require evaluations to reflect operational reality: software with critical vulnerabilities, unhandled startup crashes, or total absence of test coverage cannot be certified or recommended for production use.

---

## 2. Decision

We enforce **Deterministic Quality Gates and Fatal Flaw Guardrails** within the Deterministic Scoring Engine:

1. **Quality Gate Ceilings (Hard Score Caps):**
   - **`GATE_CRITICAL_SECURITY_BREACH`:** Triggered by any `CRITICAL` severity finding (e.g. exposed credentials, private keys, RCE CVEs). Composite score is capped at **$\le 45.0$ (Grade F)**.
   - **`GATE_BUILD_FAILURE`:** Triggered when compilation or dependency installation fails. Composite score is capped at **$\le 35.0$ (Grade F)**.
   - **`GATE_STARTUP_BOOT_CRASH`:** Triggered when the application crashes on entrypoint boot. Composite score is capped at **$\le 45.0$ (Grade F)**.
   - **`GATE_HIGH_SECURITY_DEBT`:** Triggered by multiple `HIGH` security findings without critical flaws. Composite score is capped at **$\le 65.0$ (Grade C)**.
   - **`GATE_TEST_SUITE_FAILURES`:** Triggered when the automated test suite fails. Composite score is capped at **$\le 68.0$ (Grade C)**.

2. **Cross-Dimensional Compounding Deductions:**
   - Critical security breaches compound into **Engineering Maturity** (`RULE_ENG_CRITICAL_SECURITY_DEBT`, -25 pts), reflecting lack of pre-commit hooks and pipeline controls.

3. **Empirical Metadata Binding:**
   - Real repository indicators (README presence, lockfile existence, CI/CD detection, and startup success) are bound directly to deterministic score evaluations.

4. **100% Deterministic & Transparent Attribution:**
   - Every triggered Quality Gate generates a transparent receipt item of type `QUALITY_GATE` with a unique evidence UUID and human-readable explanation in the scorecard.

---

## 3. Consequences

- **Positive:**
  - Realistic and defensible: Insecure or broken repositories fail quality gates decisively.
  - Aligned with industry standards: Mirrors enterprise gating frameworks (SonarQube Quality Gates, SLSA, OpenSSF).
  - Uncompromising and objective: AI reasoning cannot soften or bypass these deterministic ceilings.
- **Negative:**
  - Repositories with single critical flaws receive low grades (intended design behavior).

---

## 4. Compliance

- Implemented in `backend/scoring/quality_gates.py` and `backend/scoring/calculator.py`.
- Formally verified in `tests/unit/test_scoring_calculator.py`.
