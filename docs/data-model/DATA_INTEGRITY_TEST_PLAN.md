# Data Integrity & Schema Verification Test Plan

> **Document:** `DATA_INTEGRITY_TEST_PLAN.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Persistence Baseline  
> **Phase:** Phase 03 — Data Model and Persistence Design  
> **Authority:** `phases/03_DATA_MODEL.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Objective & Scope

This document specifies the automated test cases and verification procedures to ensure data integrity, relational constraints, snapshot immutability, trigger enforcement, and schema migration reversibility defined in [POSTGRES_SCHEMA_SPEC.md](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/data-model/POSTGRES_SCHEMA_SPEC.md).

These test suites will be implemented in `tests/integration/test_database_integrity.py` and `tests/integration/test_migrations.py` during Phase 05 (Foundation).

---

## 2. Master Data Integrity Test Matrix

| Test ID | Test Case Name | Target Table / Object | Invariant Tested | Verification Method | Expected Result |
|---|---|---|---|---|---|
| **DATA-TEST-01** | Repository URL Uniqueness | `repositories` | `url` is UNIQUE | Insert 2 repos with identical URL | DB raises `UniqueViolation` on 2nd insert |
| **DATA-TEST-02** | Snapshot Commit Uniqueness | `repository_snapshots` | `(repository_id, commit_sha)` UNIQUE | Insert 2 snapshots with same repo & SHA | DB raises `uq_repo_commit` violation |
| **DATA-TEST-03** | Snapshot Immutability Trigger | `repository_snapshots` | Snapshot is append-only | Execute `UPDATE` or `DELETE` on snapshot | DB trigger raises `Database Integrity Error` |
| **DATA-TEST-04** | Terminal Evaluation Seal Trigger | `evaluations` | Sealed status is immutable | `UPDATE evaluations SET error_summary='x' WHERE status='COMPLETED'` | DB trigger blocks update with exception |
| **DATA-TEST-05** | Active Evaluation State Update | `evaluations` | State transitions permitted during run | `UPDATE evaluations SET status='ANALYZING' WHERE status='INGESTING'` | Update succeeds normally |
| **DATA-TEST-06** | Evidence Append-Only Trigger | `evidence` | Evidence is immutable | Execute `UPDATE evidence SET severity='LOW'` | DB trigger blocks update with exception |
| **DATA-TEST-07** | Evidence Fingerprint Deduplication | `evidence` | `(evaluation_id, fingerprint)` UNIQUE | Insert 2 evidence items with same SHA-256 fingerprint | DB raises `uq_eval_fingerprint` violation |
| **DATA-TEST-08** | Score Clamping Check Constraint | `scores` | `overall_score BETWEEN 0.0 AND 100.0` | Insert row with `overall_score = 105.0` or `-5.0` | DB raises `CheckViolation` |
| **DATA-TEST-09** | Score Dimension Unique Constraint | `score_dimensions` | `(score_id, dimension_name)` UNIQUE | Insert 2 rows for "Security" under same `score_id` | DB raises `uq_score_dimension` violation |
| **DATA-TEST-10** | Score Dimension Receipt Integrity | `score_dimensions` | Itemized receipt valid JSONB | Insert valid receipt vs malformed JSON | Valid array persists; queries via GIN succeed |
| **DATA-TEST-11** | Scorecard Restrict on Snapshot Delete| `evaluations`, `scores` | `ON DELETE RESTRICT` protects audit | Attempt `DELETE FROM repository_snapshots` while eval exists | DB rejects deletion with FK `ForeignKeyViolation` |
| **DATA-TEST-12** | Step Duration Non-Negative Check | `evaluation_steps` | `duration_ms >= 0` | Insert row with `duration_ms = -50` | DB raises `CheckViolation` |
| **DATA-TEST-13** | AI Analysis Token Count Non-Negative | `ai_analyses` | `tokens_consumed >= 0` | Insert row with `tokens_consumed = -10` | DB raises `CheckViolation` |
| **DATA-TEST-14** | Recommendation Priority Enum | `recommendations` | Priority in (`HIGH`, `MEDIUM`, `LOW`) | Insert row with priority = `'CRITICAL'` | DB raises `InvalidTextRepresentation` (Enum) |
| **DATA-TEST-15** | Alembic Migration Roundtrip | Full Schema | Reversible DDL | Run `alembic upgrade head`, then `downgrade base`, then `upgrade head` | All migrations roll back and re-apply cleanly |

---

## 3. Detailed Test Implementations (Specification)

### Test Spec: Sealed Evaluation Immutability (DATA-TEST-04)
```python
async def test_sealed_evaluation_immutability(db_session):
    # Given an evaluation that reached COMPLETED status
    eval_record = await create_test_evaluation(db_session, status="COMPLETED")
    
    # When an update is attempted on any field
    with pytest.raises(DatabaseError) as exc_info:
        eval_record.error_summary = "Malicious retroactive tampering"
        await db_session.commit()
        
    # Then the database trigger must abort the transaction
    assert "Evaluation is sealed in terminal state" in str(exc_info.value)
```

### Test Spec: Evidence Deduplication via Fingerprint (DATA-TEST-07)
```python
async def test_evidence_fingerprint_deduplication(db_session):
    eval_id = uuid7()
    fingerprint = hashlib.sha256(b"semgrep:rule_1:file.py:10").hexdigest()
    
    # First insert succeeds
    await insert_evidence(db_session, eval_id=eval_id, fingerprint=fingerprint)
    
    # Second insert with identical fingerprint for same evaluation must fail
    with pytest.raises(IntegrityError):
        await insert_evidence(db_session, eval_id=eval_id, fingerprint=fingerprint)
```

---

## 4. Test Execution & CI Automation

- **Execution Runtime:** Integration tests execute against an ephemeral test PostgreSQL 16 container running in Docker.
- **Pre-Commit Verification:** Schema integrity and migration tests execute on every Pull Request before merge approval.
