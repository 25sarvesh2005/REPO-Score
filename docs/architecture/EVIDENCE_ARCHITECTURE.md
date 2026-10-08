# Evidence Engine Architecture

> **Document:** `EVIDENCE_ARCHITECTURE.md`  
> **Status:** Active / Architectural Contract  
> **Owner:** Core Architecture Team  
> **Referenced ADRs:** ADR-003, ADR-004, ADR-006

---

## 1. Centrality of Evidence

The **Evidence Engine** is the foundational bedrock of RepoScore. In our architectural hierarchy:
1. Raw tool outputs, metrics, and logs are **ephemeral signals**.
2. **Evidence** is the normalized, immutable, verifiable record of truth.
3. **Scores** and **AI Insights** are downstream derivations that MUST cite specific evidence items.

```mermaid
graph TD
    subgraph SignalSources ["Ephemeral Signal Producers"]
        StaticFind[Static Analyzer Findings]
        SecFind[Security & CVE Scans]
        BuildLogs[Build Outputs & Exit Codes]
        RunMetrics[Runtime Probes & Latencies]
        ResourceLogs[cgroups Telemetry & OOM Events]
    end

    subgraph EvidencePipeline ["Evidence Engine Core"]
        Normalizer[Signal Normalizer & Validator]
        Deduper[Fingerprint Generator & Deduplicator]
        Correlator[Cross-Domain Correlator]
        EvidenceDB[(Immutable Evidence Store\nPostgreSQL Table: evidence)]
    end

    subgraph EvidenceConsumers ["Strict Downstream Consumers"]
        Scorer[Deterministic Scoring Engine\n(Consumes Evidence, Emits Numbers)]
        AIReasoner[AI Reasoning Engine\n(Consumes Evidence, Emits Narrative)]
        AuditLog[Compliance & Verification Auditor]
    end

    StaticFind --> Normalizer
    SecFind --> Normalizer
    BuildLogs --> Normalizer
    RunMetrics --> Normalizer
    ResourceLogs --> Normalizer

    Normalizer --> Deduper
    Deduper --> Correlator
    Correlator --> EvidenceDB

    EvidenceDB --> Scorer
    EvidenceDB --> AIReasoner
    EvidenceDB --> AuditLog
```

---

## 2. Canonical Evidence Data Model

Every finding, measurement, and observation is normalized into the canonical `EvidenceRecord` structure:

```json
{
  "id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
  "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
  "source": "ANALYZER_SEMGREP",
  "category": "SECURITY",
  "severity": "HIGH",
  "confidence": 0.95,
  "fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "title": "Hardcoded AWS Secret Access Key",
  "description": "Detected high-entropy pattern matching AWS Secret Key format within configuration file.",
  "location": {
    "file_path": "config/aws_client.py",
    "start_line": 14,
    "end_line": 14,
    "start_col": 12,
    "end_col": 52
  },
  "raw_payload": {
    "check_id": "rules.python.secrets.aws-secret",
    "extra": {
      "metavars": {
        "$KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
      }
    }
  },
  "normalized_attributes": {
    "cwe_id": "CWE-798",
    "owasp_category": "A07:2021-Identification and Authentication Failures",
    "remediation": "Move credential to environment variable or secret manager."
  },
  "related_evidence_ids": [],
  "created_at": "2026-10-08T22:30:00Z"
}
```

### Field Definitions:
- **`id`**: Unique UUIDv7 identifier containing embedded millisecond timestamp.
- **`evaluation_id`**: Foreign key to the parent evaluation.
- **`source`**: The generating component (`INGESTION`, `TREE_SITTER`, `SEMGREP`, `RUFF`, `OSV`, `RUNTIME_PROBER`, `DOCKER_CGROUPS`).
- **`category`**: One of the 10 core dimensions: `CORRECTNESS`, `RELIABILITY`, `SECURITY`, `MAINTAINABILITY`, `TESTING`, `DOCUMENTATION`, `PERFORMANCE`, `ARCHITECTURE`, `DEPENDENCY_HEALTH`, `ENGINEERING_MATURITY`.
- **`severity`**: Impact weighting: `CRITICAL` (score blocker/fatal), `HIGH`, `MEDIUM`, `LOW`, `INFO`, or `POSITIVE` (for positive achievements, e.g., 100% test pass rate, comprehensive README).
- **`confidence`**: Floating point value $[0.0, 1.0]$. Static regex heuristic = $0.6$; compiler crash = $1.0$.
- **`fingerprint`**: SHA-256 hash derived from `(category, rule_id, file_path, line_number)`. Ensures idempotent ingestion and deduplication across multiple passes.

---

## 3. Database Schema & Indexing Strategy

In PostgreSQL, the `evidence` table is optimized for write throughput and fast categorical retrieval:

```sql
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    fingerprint CHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    location JSONB,
    raw_payload JSONB,
    normalized_attributes JSONB,
    related_evidence_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Compound index for scoring engine aggregation
CREATE INDEX idx_evidence_eval_cat_sev 
ON evidence (evaluation_id, category, severity);

-- Unique index for idempotent deduplication within an evaluation
CREATE UNIQUE INDEX idx_evidence_dedup 
ON evidence (evaluation_id, fingerprint);

-- GIN index for deep querying of raw payloads and CWE tags
CREATE INDEX idx_evidence_normalized_gin 
ON evidence USING GIN (normalized_attributes);
```

---

## 4. Immutability & Audit Guarantees

1. **Append-Only Invariant**: The database role assigned to workers has `INSERT` and `SELECT` privileges on the `evidence` table, but **`UPDATE` and `DELETE` privileges are strictly revoked**.
2. **Traceability**: Every score deduction or bonus in the final evaluation report contains an explicit link to one or more `evidence.id` values.
3. **No Unbacked Claims**: If an AI summary states *"The application suffers from memory leaks"*, the prompt synthesis engine must supply the underlying `evidence` UUID for the memory anomaly. Hallucinated findings without evidence are rejected.
