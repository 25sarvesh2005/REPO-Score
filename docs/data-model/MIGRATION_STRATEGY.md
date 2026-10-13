# Database Migration & Retention Strategy

> **Document:** `MIGRATION_STRATEGY.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Persistence Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. Alembic Migration Framework & Tooling

RepoScore uses **Alembic** alongside **SQLAlchemy 2.0 (asyncio)** for version-controlled, repeatable, and reversible database schema migrations:
- **Migration Directory:** `backend/database/migrations/versions/`
- **Configuration File:** `backend/database/alembic.ini`
- **Environment Script:** `backend/database/migrations/env.py`
- **Async Driver:** `asyncpg` for PostgreSQL connection pooling and transaction control.

---

## 2. Migration Guidelines & Policies

### 2.1 Sequential Linear Revisions
- All migration scripts MUST follow strict linear revision chains. Branching heads (`alembic merge`) are prohibited in release branches.
- File naming convention: `{revision_id}_{description}.py` (e.g., `0001_initial_15_entities.py`).

### 2.2 Strict Reversibility (`upgrade` & `downgrade`)
Every migration file MUST implement both `upgrade()` and `downgrade()` functions:
- A migration that lacks an operable `downgrade()` is rejected at the CI code review gate.
- Destructive column drops (`DROP COLUMN`) MUST be preceded by a deprecation release phase where the column is made nullable and ignored in ORM models before physical removal.

### 2.3 Idempotency & Transactional DDL
PostgreSQL supports transactional DDL. All migrations execute within a single transaction block:
- If any DDL statement fails, the entire migration aborts and rolls back, leaving the database in its previous valid schema state.
- Enum creation statements use `IF NOT EXISTS` or exception trapping to avoid duplicate type errors.

---

## 3. Initial Migration Plan (`0001_initial_schema.py`)

The initial migration establishes the foundational 15 entities defined in [POSTGRES_SCHEMA_SPEC.md](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/data-model/POSTGRES_SCHEMA_SPEC.md):

```text
Sequence of Execution in 0001:
1. Create Custom ENUM types (evaluation_status_enum, severity_level_enum, etc.)
2. Create Table: repositories
3. Create Table: repository_snapshots
4. Create Table: evaluations
5. Create Table: evaluation_steps
6. Create Table: execution_environments
7. Create Table: test_scenarios
8. Create Table: runtime_observations
9. Create Table: static_findings
10. Create Table: security_findings
11. Create Table: evidence
12. Create Table: scores
13. Create Table: score_dimensions
14. Create Table: ai_analyses
15. Create Table: recommendations
16. Create Table: evaluation_events
17. Create Performance Indexes (B-tree, GIN on JSONB)
18. Create Immutability Trigger Functions and Triggers
```

---

## 4. Data Retention, Pruning & Archiving Strategy

### 4.1 Evaluation Artifact Retention Tiers
To prevent uncontrolled database growth while preserving historical trend comparisons:

| Data Category | Primary Tables | Default Retention Period | Pruning / Archiving Action |
|---|---|---|---|
| **Core Metadata & Scores** | `repositories`, `repository_snapshots`, `evaluations`, `scores`, `score_dimensions` | **Permanent (Indefinite)** | Preserved forever for historical score trending and auditability. |
| **Normalized Evidence** | `evidence` | **Permanent (Indefinite)** | Retained as the source-of-truth backing every historical score receipt. |
| **Raw Static Findings** | `static_findings`, `security_findings` | **180 Days** | Archived or purged once evidence normalization and evaluation is finalized. |
| **High-Frequency Telemetry** | `runtime_observations` | **90 Days** | Roll up into summary metrics; purge granular time-series rows. |
| **Real-Time Event Logs** | `evaluation_events` | **30 Days** | Transient SSE playback events pruned after 30 days. |
| **Disk Snapshot Archives** | `/var/reposcore/snapshots/*` | **LRU Cache (Max 50GB)** | Ephemeral disk snapshots deleted when unreferenced; re-cloneable from GitHub. |

### 4.2 Automated Pruning Worker
An automated, bounded maintenance job runs nightly via the worker pool:
- Runs in small batches (`LIMIT 1000`) within explicit transactions to avoid table locks.
- Targets only rows where `evaluation.created_at < NOW() - INTERVAL '30 days'` for `evaluation_events`.
- Respects `ON DELETE RESTRICT` constraints, ensuring active or referenced scores are never orphaned.
