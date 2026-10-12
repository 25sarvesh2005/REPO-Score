# PostgreSQL 16+ Physical Schema Specification

> **Document:** `POSTGRES_SCHEMA_SPEC.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Persistence Baseline  
> **Phase:** Phase 03 — Data Model and Persistence Design  
> **Authority:** `phases/03_DATA_MODEL.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Overview & PostgreSQL Standards

This document specifies the complete physical DDL, types, constraints, indexes, and database-level immutability triggers for RepoScore on **PostgreSQL 16+**:
- **Identifier Types:** All entity identifiers use `UUID` (generating RFC 9562 time-ordered `UUIDv7` in application code, with `gen_random_uuid()` as fallback).
- **Timezone Standardization:** All timestamps are strictly `TIMESTAMPTZ` (UTC).
- **Numeric Precision:** Scores use `NUMERIC(5, 2)` to avoid IEEE 754 floating-point inaccuracies.
- **JSON Standard:** Semi-structured data uses `JSONB` backed by GIN indexes.

---

## 2. Enums and Custom Types

```sql
-- Evaluation FSM State Enum (17 States)
CREATE TYPE evaluation_status_enum AS ENUM (
    'QUEUED',
    'INGESTING',
    'ANALYZING',
    'BUILDING',
    'STARTING',
    'TESTING',
    'OBSERVING',
    'SCORING',
    'AI_INTERPRETATION',
    'COMPLETED',
    'PARTIALLY_COMPLETED',
    'BUILD_FAILED',
    'STARTUP_FAILED',
    'FAILED',
    'TIMEOUT',
    'CANCELLED',
    'UNSUPPORTED'
);

-- Evaluation Step Status Enum
CREATE TYPE step_status_enum AS ENUM (
    'PENDING',
    'IN_PROGRESS',
    'SUCCESS',
    'FAILURE',
    'SKIPPED',
    'CANCELLED'
);

-- Normalized Severity Enum
CREATE TYPE severity_level_enum AS ENUM (
    'CRITICAL',
    'HIGH',
    'MEDIUM',
    'LOW',
    'INFO'
);

-- Evidence Category Enum (10 Dimensions)
CREATE TYPE evidence_category_enum AS ENUM (
    'CORRECTNESS',
    'SECURITY',
    'RELIABILITY',
    'TESTING',
    'MAINTAINABILITY',
    'ARCHITECTURE',
    'PERFORMANCE',
    'DEPENDENCY_HEALTH',
    'DOCUMENTATION',
    'ENGINEERING_MATURITY'
);

-- Test Scenario Origin Enum
CREATE TYPE scenario_origin_enum AS ENUM (
    'REPOSITORY_PROVIDED',
    'PLATFORM_DETERMINISTIC',
    'AI_GENERATED',
    'RUNTIME_SCENARIO',
    'SECURITY'
);

-- Recommendation Priority Enum
CREATE TYPE priority_level_enum AS ENUM (
    'HIGH',
    'MEDIUM',
    'LOW'
);
```

---

## 3. Physical Table Definitions (All 15 Entities)

```sql
-- ============================================================================
-- 1. REPOSITORIES
-- ============================================================================
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR(512) NOT NULL UNIQUE,
    provider VARCHAR(32) NOT NULL DEFAULT 'github',
    owner VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    default_branch VARCHAR(64) NOT NULL DEFAULT 'main',
    is_private BOOLEAN NOT NULL DEFAULT FALSE,
    stars_count INTEGER NOT NULL DEFAULT 0 CHECK (stars_count >= 0),
    forks_count INTEGER NOT NULL DEFAULT 0 CHECK (forks_count >= 0),
    open_issues_count INTEGER NOT NULL DEFAULT 0 CHECK (open_issues_count >= 0),
    license_spdx VARCHAR(64),
    primary_language VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2. REPOSITORY SNAPSHOTS (Immutable commit references)
-- ============================================================================
CREATE TABLE repository_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_sha CHAR(40) NOT NULL,
    tree_hash CHAR(64) NOT NULL,
    branch_or_tag VARCHAR(128),
    storage_path VARCHAR(512) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    file_count INTEGER NOT NULL CHECK (file_count >= 0),
    detected_languages JSONB NOT NULL DEFAULT '{}',
    detected_frameworks JSONB NOT NULL DEFAULT '[]',
    detected_entrypoints JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_repo_commit UNIQUE (repository_id, commit_sha)
);

-- ============================================================================
-- 3. EVALUATIONS (Master Orchestration Record)
-- ============================================================================
CREATE TABLE evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    snapshot_id UUID NOT NULL REFERENCES repository_snapshots(id) ON DELETE RESTRICT,
    status evaluation_status_enum NOT NULL DEFAULT 'QUEUED',
    correlation_id UUID NOT NULL,
    trigger_source VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
    worker_id VARCHAR(64),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER CHECK (duration_ms >= 0),
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 4. EVALUATION STEPS (Granular Audit Log)
-- ============================================================================
CREATE TABLE evaluation_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    step_name VARCHAR(64) NOT NULL,
    status step_status_enum NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER CHECK (duration_ms >= 0),
    exit_code INTEGER,
    error_message TEXT,
    step_metadata JSONB NOT NULL DEFAULT '{}'
);

-- ============================================================================
-- 5. EXECUTION ENVIRONMENTS (Sandbox Confinement Provenance)
-- ============================================================================
CREATE TABLE execution_environments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    container_id VARCHAR(128) NOT NULL,
    base_image VARCHAR(256) NOT NULL,
    runtime_type VARCHAR(32) NOT NULL DEFAULT 'DOCKER_RUNC',
    cpu_quota NUMERIC(4, 2) NOT NULL DEFAULT 2.0,
    memory_limit_bytes BIGINT NOT NULL DEFAULT 2147483648, -- 2GB
    pids_limit INTEGER NOT NULL DEFAULT 128,
    network_policy VARCHAR(32) NOT NULL DEFAULT 'NONE',
    capabilities_dropped TEXT[] NOT NULL DEFAULT ARRAY['ALL']::TEXT[],
    uid_enforced INTEGER NOT NULL DEFAULT 10001,
    gid_enforced INTEGER NOT NULL DEFAULT 10001,
    seccomp_profile_digest CHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 6. TEST SCENARIOS (Executed Probes & Test Suites)
-- ============================================================================
CREATE TABLE test_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    scenario_type scenario_origin_enum NOT NULL,
    command_executed TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    test_count INTEGER NOT NULL DEFAULT 0 CHECK (test_count >= 0),
    pass_count INTEGER NOT NULL DEFAULT 0 CHECK (pass_count >= 0),
    fail_count INTEGER NOT NULL DEFAULT 0 CHECK (fail_count >= 0),
    stdout_excerpt TEXT,
    stderr_excerpt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 7. RUNTIME OBSERVATIONS (Telemetry & Health Metrics)
-- ============================================================================
CREATE TABLE runtime_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    observation_type VARCHAR(64) NOT NULL,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_value_numeric NUMERIC(12, 4),
    metric_value_string TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

-- ============================================================================
-- 8. STATIC FINDINGS (Raw Linter & AST Scanner Findings)
-- ============================================================================
CREATE TABLE static_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    tool_name VARCHAR(64) NOT NULL,
    tool_version VARCHAR(32),
    rule_id VARCHAR(128) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    start_line INTEGER CHECK (start_line >= 1),
    end_line INTEGER CHECK (end_line >= start_line),
    start_col INTEGER CHECK (start_col >= 1),
    end_col INTEGER CHECK (end_col >= 1),
    raw_severity VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    snippet TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 9. SECURITY FINDINGS (CVEs, Secrets & Vulnerabilities)
-- ============================================================================
CREATE TABLE security_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    vulnerability_id VARCHAR(128) NOT NULL,
    package_name VARCHAR(255),
    installed_version VARCHAR(64),
    fixed_version VARCHAR(64),
    cvss_score NUMERIC(3, 1) CHECK (cvss_score >= 0.0 AND cvss_score <= 10.0),
    severity severity_level_enum NOT NULL,
    cwe_ids TEXT[] DEFAULT '{}',
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 10. EVIDENCE (Canonical Normalized Evidence - Append-Only)
-- ============================================================================
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,
    category evidence_category_enum NOT NULL,
    severity severity_level_enum NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    fingerprint CHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    location JSONB,
    raw_payload JSONB,
    normalized_attributes JSONB NOT NULL DEFAULT '{}',
    related_evidence_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_eval_fingerprint UNIQUE (evaluation_id, fingerprint)
);

-- ============================================================================
-- 11. SCORES (Deterministic Composite Scorecard)
-- ============================================================================
CREATE TABLE scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL UNIQUE REFERENCES evaluations(id) ON DELETE RESTRICT,
    scoring_version VARCHAR(16) NOT NULL DEFAULT '1.0.0',
    overall_score NUMERIC(5, 2) NOT NULL CHECK (overall_score >= 0.0 AND overall_score <= 100.0),
    grade VARCHAR(4) NOT NULL CHECK (grade IN ('A+', 'A', 'B', 'C', 'D', 'F')),
    total_deductions NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    total_credits NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 12. SCORE DIMENSIONS (Itemized Breakdown for 10 Dimensions)
-- ============================================================================
CREATE TABLE score_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    score_id UUID NOT NULL REFERENCES scores(id) ON DELETE CASCADE,
    dimension_name VARCHAR(32) NOT NULL,
    score NUMERIC(5, 2) NOT NULL CHECK (score >= 0.0 AND score <= 100.0),
    weight NUMERIC(4, 3) NOT NULL CHECK (weight >= 0.0 AND weight <= 1.0),
    base_score NUMERIC(5, 2) NOT NULL DEFAULT 100.0,
    itemized_receipt JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_score_dimension UNIQUE (score_id, dimension_name)
);

-- ============================================================================
-- 13. AI ANALYSES (Qualitative Executive Narrative)
-- ============================================================================
CREATE TABLE ai_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL UNIQUE REFERENCES evaluations(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL DEFAULT 'ollama',
    model_name VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(16) NOT NULL DEFAULT '1.0.0',
    executive_summary TEXT NOT NULL,
    architectural_assessment TEXT NOT NULL,
    runtime_failure_root_cause TEXT,
    security_risk_narrative TEXT NOT NULL,
    tokens_consumed INTEGER CHECK (tokens_consumed >= 0),
    duration_ms INTEGER CHECK (duration_ms >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 14. RECOMMENDATIONS (Actionable Remediation Guidance)
-- ============================================================================
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_analysis_id UUID NOT NULL REFERENCES ai_analyses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    category evidence_category_enum NOT NULL,
    priority priority_level_enum NOT NULL,
    explanation TEXT NOT NULL,
    actionable_steps JSONB NOT NULL DEFAULT '[]',
    related_evidence_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 15. EVALUATION EVENTS (Real-Time SSE Event Log)
-- ============================================================================
CREATE TABLE evaluation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    emitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Performance Indexes

```sql
-- Indexes on Repositories
CREATE INDEX idx_repos_owner_name ON repositories (owner, name);

-- Indexes on Repository Snapshots
CREATE INDEX idx_snapshots_repo_id ON repository_snapshots (repository_id);
CREATE INDEX idx_snapshots_commit ON repository_snapshots (commit_sha);
CREATE INDEX idx_snapshots_languages ON repository_snapshots USING gin (detected_languages);

-- Indexes on Evaluations
CREATE INDEX idx_evals_repo_id ON evaluations (repository_id);
CREATE INDEX idx_evals_snapshot_id ON evaluations (snapshot_id);
CREATE INDEX idx_evals_status ON evaluations (status);
CREATE INDEX idx_evals_correlation_id ON evaluations (correlation_id);
CREATE INDEX idx_evals_created_at ON evaluations (created_at DESC);

-- Indexes on Evaluation Steps
CREATE INDEX idx_steps_eval_id ON evaluation_steps (evaluation_id, started_at);

-- Indexes on Static & Security Findings
CREATE INDEX idx_static_findings_eval ON static_findings (evaluation_id, file_path);
CREATE INDEX idx_sec_findings_eval ON security_findings (evaluation_id, severity);

-- Indexes on Evidence
CREATE INDEX idx_evidence_eval_id ON evidence (evaluation_id);
CREATE INDEX idx_evidence_category_severity ON evidence (category, severity);
CREATE INDEX idx_evidence_location ON evidence USING gin (location);
CREATE INDEX idx_evidence_attributes ON evidence USING gin (normalized_attributes);

-- Indexes on Scores & Dimensions
CREATE INDEX idx_scores_eval_id ON scores (evaluation_id);
CREATE INDEX idx_score_dims_score_id ON score_dimensions (score_id);

-- Indexes on Telemetry & Events
CREATE INDEX idx_runtime_obs_eval_time ON runtime_observations (evaluation_id, sampled_at);
CREATE INDEX idx_events_eval_time ON evaluation_events (evaluation_id, emitted_at);
```

---

## 5. Database Immutability Triggers

To strictly enforce ADR-010 and data integrity invariants, database-level triggers prevent mutation or deletion of sealed evaluations and append-only evidence.

```sql
-- ============================================================================
-- Immutability Function: Sealed Terminal State Protection
-- ============================================================================
CREATE OR REPLACE FUNCTION enforce_sealed_evaluation_immutability()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if existing evaluation is already in a terminal state
    IF OLD.status IN ('COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED', 'UNSUPPORTED') THEN
        RAISE EXCEPTION 'Database Integrity Error: Evaluation % is sealed in terminal state % and cannot be modified.',
            OLD.id, OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_eval_terminal_immutability
BEFORE UPDATE OR DELETE ON evaluations
FOR EACH ROW EXECUTE FUNCTION enforce_sealed_evaluation_immutability();

-- ============================================================================
-- Immutability Function: Evidence & Score Append-Only Enforcement
-- ============================================================================
CREATE OR REPLACE FUNCTION enforce_evidence_immutability()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Database Integrity Error: % records are strictly append-only and cannot be updated or deleted.',
        TG_TABLE_NAME;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_evidence_immutability
BEFORE UPDATE OR DELETE ON evidence
FOR EACH ROW EXECUTE FUNCTION enforce_evidence_immutability();

CREATE TRIGGER trg_scores_immutability
BEFORE UPDATE OR DELETE ON scores
FOR EACH ROW EXECUTE FUNCTION enforce_evidence_immutability();

CREATE TRIGGER trg_score_dimensions_immutability
BEFORE UPDATE OR DELETE ON score_dimensions
FOR EACH ROW EXECUTE FUNCTION enforce_evidence_immutability();

CREATE TRIGGER trg_snapshot_immutability
BEFORE UPDATE OR DELETE ON repository_snapshots
FOR EACH ROW EXECUTE FUNCTION enforce_evidence_immutability();
```
