# Deterministic Scoring Engine Architecture

> **Document:** `SCORING_ARCHITECTURE.md`  
> **Status:** Active / Architectural Contract  
> **Owner:** Core Architecture Team  
> **Referenced ADRs:** ADR-003, ADR-004

---

## 1. Principles of Deterministic Scoring

The Scoring Engine is purely mathematical, rule-driven, and reproducible.
1. **Zero AI Influence**: Large Language Models and probabilistic algorithms are strictly barred from calculating, altering, or weighting numerical scores.
2. **100% Deterministic & Reproducible**: Given the same set of evidence items and scoring ruleset version, the calculated score will be bit-for-bit identical every time.
3. **Evidence-Backed**: Every point deducted or awarded must reference one or more specific `evidence.id` entries. Unbacked penalties are mathematically impossible.
4. **Transparent & Explainable**: The user is provided with a complete itemized receipt explaining every deduction and credit.

```mermaid
graph TD
    EvidenceDB[(PostgreSQL Evidence Store)] --> Filter[Filter by Category & Confidence]

    subgraph ScoringCore ["Deterministic Scoring Core (Version: 1.0.0)"]
        Filter --> Dim1[1. Correctness Scorer]
        Filter --> Dim2[2. Reliability Scorer]
        Filter --> Dim3[3. Security Scorer]
        Filter --> Dim4[4. Maintainability Scorer]
        Filter --> Dim5[5. Testing Scorer]
        Filter --> Dim6[6. Documentation Scorer]
        Filter --> Dim7[7. Performance Scorer]
        Filter --> Dim8[8. Architecture Scorer]
        Filter --> Dim9[9. Dependency Health Scorer]
        Filter --> Dim10[10. Engineering Maturity Scorer]

        Dim1 --> Weights[Weighted Aggregator]
        Dim2 --> Weights
        Dim3 --> Weights
        Dim4 --> Weights
        Dim5 --> Weights
        Dim6 --> Weights
        Dim7 --> Weights
        Dim8 --> Weights
        Dim9 --> Weights
        Dim10 --> Weights

        Weights --> Composite[Overall Composite Score (0 - 100)]
    end

    Composite --> Persistence[(PostgreSQL: scores & score_dimensions)]
```

---

## 2. The 10 Evaluation Dimensions & Weights

The overall repository score is a composite weighted sum across 10 discrete engineering dimensions:

| Dimension | Weight ($w_d$) | Description & Primary Evidence Signals |
|---|---|---|
| **1. Correctness** | 0.18 | Build passes, application runs, zero syntax errors, test suite passes, zero crash traces. |
| **2. Security** | 0.16 | Zero critical/high CVEs, no hardcoded secrets, no OWASP vulnerabilities, safe crypto. |
| **3. Reliability** | 0.14 | Graceful error handling, steady memory under synthetic load, clean SIGTERM exit, error rates. |
| **4. Testing** | 0.12 | Code coverage %, test-to-code volume ratio, automated unit/integration test presence. |
| **5. Maintainability** | 0.10 | Cyclomatic/cognitive complexity, function length, comment clarity, linter clean. |
| **6. Architecture** | 0.08 | Absence of circular dependencies, modular separation of concerns, clean layer boundaries. |
| **7. Performance** | 0.06 | Cold startup latency, idle/load memory usage, p95/p99 HTTP response times, CPU efficiency. |
| **8. Dependency Health**| 0.06 | Minimal dependency bloat, pinned versions, actively maintained dependencies, zero deprecated packages. |
| **9. Documentation** | 0.05 | Comprehensive README, setup/run guides, API reference, docstrings on exported functions. |
| **10. Engineering Maturity**| 0.05 | GitHub Actions / CI workflows present, commit history hygiene, issue templates, semantic versioning. |
| **Total** | **1.00** | $\sum w_d = 1.00$ |

---

## 3. Mathematical Scoring Formulation

### 3.1 Dimension Score Calculation
Each dimension $d \in \{1 \dots 10\}$ begins at a baseline of 100 points. Penalties are subtracted and positive credits are added:

$$S_d = \text{Clamp}_{[0, 100]}\left( 100 - \sum_{i \in \text{Deductions}_d} P_i + \sum_{j \in \text{Credits}_d} C_j \right)$$

Where each individual penalty $P_i$ is computed from evidence severity, impact factor, and confidence:

$$P_i = \text{SeverityBase}(\text{sev}_i) \times \text{Confidence}_i \times \text{ImpactFactor}_i$$

### 3.2 Severity Penalty Matrix

| Severity Level | Base Penalty Range | Description / Examples |
|---|---|---|
| `CRITICAL` | 30 – 50 pts | Build failure, crash on startup, plaintext private key, remote code execution CVE. |
| `HIGH` | 15 – 25 pts | High CVE without known exploit, circular dependency cycle, test suite failure. |
| `MEDIUM` | 5 – 10 pts | High cyclomatic complexity, lack of test coverage (<50%), memory spike under load. |
| `LOW` | 1 – 3 pts | Code style violation, missing docstring on public function, unpinned dependency minor version. |
| `INFO` | 0 pts | Informational finding; zero score penalty. |

### 3.3 Positive Credits / Bonuses
Repositories are rewarded for exemplary engineering practices (bounded so $S_d \le 100$):
- Comprehensive test coverage (>80%): $+10\text{ pts}$
- Zero lint/static analysis violations across codebase: $+10\text{ pts}$
- Clean graceful shutdown within 2 seconds: $+5\text{ pts}$
- Complete OpenAPI specification documentation: $+5\text{ pts}$

### 3.4 Overall Composite Score
The final repository score is defined by:

$$\text{Score}_{\text{overall}} = \sum_{d=1}^{10} w_d \times S_d$$

---

## 4. Scorecard Schema & Explainability Receipt

When the score is computed, an itemized receipt is stored in PostgreSQL and delivered to the user interface:

```json
{
  "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
  "scoring_version": "1.0.0",
  "overall_score": 84.6,
  "grade": "B+",
  "dimensions": {
    "SECURITY": {
      "score": 75.0,
      "weight": 0.16,
      "deductions": [
        {
          "evidence_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
          "points": -20.0,
          "reason": "Hardcoded AWS Secret Access Key in config/aws_client.py:14"
        },
        {
          "evidence_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492044",
          "points": -5.0,
          "reason": "Vulnerable dependency: requests <= 2.25.1 (CVE-2023-32681)"
        }
      ],
      "credits": []
    },
    "CORRECTNESS": {
      "score": 95.0,
      "weight": 0.18,
      "deductions": [
        {
          "evidence_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492099",
          "points": -5.0,
          "reason": "1 out of 42 unit tests failed: test_auth_expiration"
        }
      ],
      "credits": []
    }
  }
}
```

This guarantees that every repository owner understands exactly **why** their project received their score and **what specific lines of code** must be resolved to improve it.

---

## 5. Strict Empirical Auditability & Evidence Traceability (ADR-003)

In accordance with ADR-003, all score calculations are strictly derived from empirical findings:
1. Every score deduction must cite an authentic `evidence.id` record persisted in the database.
2. Synthetic score ceilings or arbitrary caps without direct evidence attribution are strictly prohibited.
3. Repositories are evaluated across static structure (hygiene, documentation, test suites, lockfiles) and dynamic sandbox execution (build, startup, runtime tests, resource consumption), ensuring that all score adjustments reflect verifiable empirical facts.

