# ADR-006: PostgreSQL Relational Persistence

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Data Architecture & Core Engineering Team  
> **Consulted:** Systems Leads  

---

## Context
RepoScore must persist structured entities with strict relational integrity (repositories, commit snapshots, evaluations, evaluation steps, deterministic scores) alongside semi-structured, heterogeneous telemetry (raw analyzer outputs, AST metrics, runtime logs, container telemetry). We need a robust, open-source persistence engine capable of handling relational joins, ACID transactions, and fast JSON querying without running multiple disparate databases.

---

## Decision
We select **PostgreSQL 16+** as the primary datastore for RepoScore:
- Relational schema for core domain entities (`repositories`, `repository_snapshots`, `evaluations`, `evaluation_steps`, `scores`, `score_dimensions`).
- Native `JSONB` columns for semi-structured payloads (`evidence.location`, `evidence.raw_payload`, `runtime_observations.metrics`).
- GIN (Generalized Inverted Index) indexing on JSONB columns to enable performant filtering by analyzer metadata, CWE tags, and vulnerability fingerprints.
- Asynchronous database access via Python's `asyncpg` driver managed through `SQLAlchemy 2.0` (async engine) with schema migrations managed via `Alembic`.

---

## Alternatives Considered
1. **MongoDB / Pure NoSQL Document Store**:
   - *Pros*: Schema-less flexibility for analyzer findings.
   - *Cons*: Weak relational integrity across evaluations and snapshots, lacks mature transaction isolation for multi-step state machines, additional operational infrastructure.
2. **SQLite (for all environments)**:
   - *Pros*: Zero external daemon.
   - *Cons*: File locking issues under concurrent multi-worker writes; unsuitable for distributed or horizontally-scaled deployments.
3. **Dual Datastore (Postgres for relational + Elasticsearch for findings)**:
   - *Rejected*: Premature optimization. Postgres JSONB with GIN indexing easily handles millions of findings without the operational burden of a separate search cluster.

---

## Consequences
- **Positive**:
  - Unified datastore: Eliminates dual-write synchronization bugs.
  - ACID guarantees ensure state machine transitions are always recorded reliably.
  - Native JSONB combines relational rigour with document flexibility.
- **Negative**:
  - Requires running a PostgreSQL service locally (mitigated via standard Docker Compose setup).

---

## Security Impact
- Mature user/role privilege management: Workers can be granted read/insert privileges on evidence tables while revoking update/delete rights to enforce immutability.
- Native parameterized queries prevent SQL injection vulnerabilities.

---

## Operational Impact
- Standard backup and restore procedures (`pg_dump`, WAL archiving).
- Lightweight footprint and predictable memory utilization.
