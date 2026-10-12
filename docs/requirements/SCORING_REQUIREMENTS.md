# Deterministic Scoring Requirements Specification (SCORE)

> **Document:** `SCORING_REQUIREMENTS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Requirements Baseline  
> **Phase:** Phase 01 — Requirements Engineering  
> **Authority:** `phases/01_REQUIREMENTS.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Scoring Principles

RepoScore's evaluation model is founded upon **Mathematical Determinism and Complete Traceability**:
1. **Zero AI Infiltration:** Large Language Models and probabilistic algorithms are strictly prohibited from calculating, weighting, or adjusting numerical scores.
2. **100% Deterministic & Reproducible:** The scoring engine takes normalized evidence records and scoring rule parameters as input, producing bit-for-bit identical scores on every calculation.
3. **Evidence-Backed Deductions & Credits:** Every deduction and credit MUST link to at least one valid `evidence_id`. Unbacked point adjustments are mathematically impossible.
4. **Complete Itemized Receipts:** The user is provided with a transparent receipt for each dimension detailing base points, deductions, and credits.

---

## 2. The 10 Evaluation Dimensions & Weights

### SCORE-001: The 10 Evaluation Dimensions Catalog
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** The system SHALL evaluate repositories across exactly 10 discrete engineering dimensions with normalized weights summing to 1.00:

| Dimension Identifier | Dimension Name | Weight ($w_d$) | Description & Primary Evidence Signals |
|---|---|---|---|
| `DIM_CORRECTNESS` | **Correctness** | 0.18 | Build passes, app boots, zero syntax errors, test suite passes, zero crash traces. |
| `DIM_SECURITY` | **Security** | 0.16 | Zero critical/high CVEs, no hardcoded secrets, no OWASP Top 10 vulnerabilities, safe crypto. |
| `DIM_RELIABILITY` | **Reliability** | 0.14 | Graceful error handling, steady memory under load, clean SIGTERM exit, low runtime error rates. |
| `DIM_TESTING` | **Testing** | 0.12 | Code coverage %, test-to-code volume ratio, automated unit and integration test presence. |
| `DIM_MAINTAINABILITY` | **Maintainability** | 0.10 | Cyclomatic/cognitive complexity, function length, comment clarity, linter cleanliness. |
| `DIM_ARCHITECTURE` | **Architecture** | 0.08 | Absence of circular dependencies, modular separation of concerns, clean layer boundaries. |
| `DIM_PERFORMANCE` | **Performance** | 0.06 | Cold startup latency, idle/load memory usage, p95/p99 HTTP response times, CPU efficiency. |
| `DIM_DEPENDENCY_HEALTH`| **Dependency Health** | 0.06 | Minimal dependency bloat, pinned versions, actively maintained dependencies, zero deprecated packages. |
| `DIM_DOCUMENTATION` | **Documentation** | 0.05 | Comprehensive README, setup/run guides, API reference, docstrings on exported functions. |
| `DIM_ENGINEERING_MATURITY`| **Engineering Maturity** | 0.05 | CI workflows (GitHub Actions), commit history hygiene, issue templates, semantic versioning. |
| **TOTAL** | — | **1.00** | $\sum_{d=1}^{10} w_d = 1.00$ |

- **Acceptance Criteria:**
  ```gherkin
  Given the scoring engine initialization
  When the dimension weight configuration is loaded
  Then exactly 10 dimensions must be registered
  And the sum of all dimension weights must equal 1.000000 within IEEE 754 precision
  ```

---

## 3. Mathematical Scoring Formulation

### SCORE-002: Dimension Score Calculation Formula
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** Each dimension score $S_d$ ($d \in \{1 \dots 10\}$) begins at a baseline of 100.0 points. Deductions are subtracted and credits are added, clamped to the range $[0.0, 100.0]$:
  $$S_d = \text{Clamp}_{[0.0, 100.0]}\left( 100.0 - \sum_{i \in \text{Deductions}_d} P_i + \sum_{j \in \text{Credits}_d} C_j \right)$$
- **Acceptance Criteria:**
  ```gherkin
  Given a dimension with total deductions of 120 points and zero credits
  When the dimension score is computed
  Then the score must clamp to 0.0
  And must not be negative
  ```

### SCORE-003: Composite Score Calculation Formula
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** The overall composite score $S_{\text{overall}}$ is computed as the weighted sum of all 10 clamped dimension scores:
  $$S_{\text{overall}} = \text{Clamp}_{[0.0, 100.0]}\left( \sum_{d=1}^{10} w_d \cdot S_d \right)$$
  The composite score SHALL be rounded to one decimal place for presentation (e.g., `87.4`).

### SCORE-004: Standard Letter Grade Mapping
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** The system SHALL map the overall composite score to a standard letter grade:
  - `A+`: $95.0 \le S_{\text{overall}} \le 100.0$
  - `A`: $85.0 \le S_{\text{overall}} < 95.0$
  - `B`: $70.0 \le S_{\text{overall}} < 85.0$
  - `C`: $55.0 \le S_{\text{overall}} < 70.0$
  - `D`: $40.0 \le S_{\text{overall}} < 55.0$
  - `F`: $0.0 \le S_{\text{overall}} < 40.0$

### SCORE-005: Severity Penalty Multipliers
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** Penalties for negative evidence items SHALL scale by normalized severity levels:
  - `CRITICAL`: Base deduction factor $\times 25.0$
  - `HIGH`: Base deduction factor $\times 15.0$
  - `MEDIUM`: Base deduction factor $\times 8.0$
  - `LOW`: Base deduction factor $\times 3.0$
  - `INFO`: Base deduction factor $\times 0.0$ (informational only)

### SCORE-006: Confidence Weighting of Evidence Penalties
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** Deductions SHALL be weighted by the analyzer's confidence rating $c \in [0.0, 1.0]$:
  $$P_i = \text{BasePenalty} \times \text{SeverityMultiplier} \times c_i$$
  Heuristic findings with lower confidence will deduct fewer points than deterministic compiler errors ($c = 1.0$).

---

## 4. Scoring Engine Invariants & Constraints

### SCORE-007: AI Model Scoring Prohibition
- **Priority:** P0
- **Category:** Core Integrity
- **Description:** AI models MUST NOT compute, suggest, override, or alter numerical dimension scores or the composite score under any circumstance.
- **Acceptance Criteria:**
  ```gherkin
  Given an AI provider generating an evaluation summary
  When the scoring engine persists the final scorecard
  Then the scores in database table "scores" must originate 100% from the deterministic calculator
  And no AI-provided numerical score may be written to the score fields
  ```

### SCORE-008: Scoring Ruleset Versioning
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** Every scorecard MUST persist the scoring ruleset semver string (e.g. `1.0.0`). Any modification to scoring formulas, dimension weights, or deduction matrices requires bumping the version.
- **Acceptance Criteria:**
  ```gherkin
  Given a scored evaluation record
  When the score record is retrieved from the database
  Then the "scoring_version" column must match the active scoring engine version string
  ```

### SCORE-009: Score Reproducibility Invariant
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** Re-evaluating the scoring calculation on the exact same set of evidence rows using the same scoring ruleset version MUST produce the identical composite score and dimension breakdown.

### SCORE-010: Evidence Attribution Invariant
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** Every line item in `score_deductions` and `score_credits` MUST contain a valid foreign key referencing an existing `evidence_id` in the database. Orphan deductions without evidence attribution MUST be rejected.

---

## 5. Dimension-Specific Rules & Penalties

### SCORE-011: Correctness Scoring Rules
- **Priority:** P0
- **Description:**
  - Build failure: Deduct 50.0 points ($c=1.0$)
  - Startup crash: Deduct 40.0 points ($c=1.0$)
  - Syntax errors: Deduct 10.0 points per error
  - Test suite failure: Deduct 20.0 points $\times$ failure ratio ($c=1.0$)
  - Successful build and clean startup: Award 10.0 credit points

### SCORE-012: Security Scoring Rules
- **Priority:** P0
- **Description:**
  - Critical CVE (CVSS 9.0+): Deduct 30.0 points per CVE
  - High CVE (CVSS 7.0–8.9): Deduct 15.0 points per CVE
  - Hardcoded secret detected: Deduct 25.0 points per secret
  - OWASP Top 10 violation (SQL injection, SSRF, command injection): Deduct 20.0 points
  - Medium CVE: Deduct 8.0 points

### SCORE-013: Reliability Scoring Rules
- **Priority:** P1
- **Description:**
  - Runtime crash / unhandled exception: Deduct 25.0 points
  - Memory leak indication under synthetic load: Deduct 20.0 points
  - Process hangs on SIGTERM: Deduct 15.0 points
  - Clean shutdown on SIGTERM: Award 10.0 credit points

### SCORE-014: Testing Scoring Rules
- **Priority:** P1
- **Description:**
  - Zero test files present in repository: Deduct 40.0 points
  - Test coverage < 50%: Deduct 20.0 points
  - Test coverage >= 80%: Award 15.0 credit points
  - Automated integration test suite present: Award 10.0 credit points

### SCORE-015: Maintainability Scoring Rules
- **Priority:** P1
- **Description:**
  - Cognitive complexity > 25 on functions: Deduct 5.0 points per function
  - Excessive file length (> 1000 lines): Deduct 5.0 points per file
  - Linter errors (Ruff/ESLint): Deduct 1.0 point per error (capped at 20.0 points)

### SCORE-016: Architecture Scoring Rules
- **Priority:** P1
- **Description:**
  - Circular module imports detected: Deduct 15.0 points per cycle
  - God classes (> 50 methods / 2000 lines): Deduct 10.0 points
  - Clean layer separation: Award 10.0 credit points

### SCORE-017: Performance Scoring Rules
- **Priority:** P1
- **Description:**
  - Slow cold startup (> 10.0s for API): Deduct 15.0 points
  - Excessive idle memory (> 500MB): Deduct 15.0 points
  - High HTTP p95 latency (> 500ms): Deduct 15.0 points
  - Fast cold startup (< 1.0s): Award 10.0 credit points

### SCORE-018: Dependency Health Scoring Rules
- **Priority:** P1
- **Description:**
  - Unpinned dependencies in production manifests: Deduct 15.0 points
  - Deprecated or archived packages: Deduct 10.0 points per package
  - Up-to-date lockfile present (`poetry.lock`, `package-lock.json`): Award 10.0 credit points

### SCORE-019: Documentation Scoring Rules
- **Priority:** P2
- **Description:**
  - Missing README: Deduct 40.0 points
  - README lacking installation instructions: Deduct 15.0 points
  - Exported functions lacking docstrings: Deduct 0.5 points per function (capped at 20.0 points)
  - Comprehensive documentation with examples: Award 15.0 credit points

### SCORE-020: Engineering Maturity Scoring Rules
- **Priority:** P2
- **Description:**
  - No CI workflow configuration: Deduct 30.0 points
  - Active GitHub Actions / CI workflow: Award 20.0 credit points
  - Issue templates / contributing guidelines: Award 10.0 credit points
  - Clean Git commit history (semantic commits): Award 10.0 credit points

---

## 6. Score Explainability & Itemized Receipts

### SCORE-021: Itemized Receipt Generation
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** For every dimension, the system SHALL generate a structured itemized receipt:
  ```json
  {
    "dimension": "Security",
    "base_score": 100.0,
    "deductions": [
      {
        "evidence_id": "01925b4a-e011-7000-8000-000000000001",
        "rule": "RULE_CRITICAL_CVE",
        "description": "Critical CVE-2023-32681 detected in requests==2.19.1",
        "points_deducted": 30.0
      }
    ],
    "credits": [],
    "final_dimension_score": 70.0
  }
  ```

### SCORE-022: Explainable Dimension Narratives
- **Priority:** P1
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** The system SHALL provide a machine-readable summary of the top 3 positive contributors and top 3 negative contributors for each dimension.

### SCORE-023: Partial Evaluation Scoring Adjustments
- **Priority:** P0
- **Owner Component:** Scoring Engine (`backend.scoring.calculator`)
- **Description:** In evaluations where `BUILD_FAILED` or `STARTUP_FAILED` occurred, dimensions that require runtime execution (`Performance`, `Reliability`) SHALL be flagged with `status: "EVALUATION_INCOMPLETE"` and marked with an appropriate penalty rather than crashing the scoring engine.

### SCORE-024: Scorecard Immutability
- **Priority:** P0
- **Owner Component:** Persistence Layer (`backend.database.core`)
- **Description:** Once written to `scores` and `score_dimensions` tables for a completed evaluation, score records SHALL be immutable.
