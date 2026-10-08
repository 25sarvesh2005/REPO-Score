# ADR-010: Immutable Repository Snapshots

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Data Architecture & Security Team  
> **Consulted:** Core Systems Team  

---

## Context
When evaluating a repository across multiple stages (static analysis, dependency analysis, container builds, runtime probing), the source files must remain strictly identical across all steps. Furthermore, if a user re-evaluates a historical report or inspects line-level evidence weeks later, the exact commit and file state must be verifiable.

If workers analyze a mutable git branch that changes mid-evaluation, or if untrusted build processes inside the sandbox modify or delete source files on disk, subsequent analyzers will evaluate corrupt state, leading to non-reproducible, invalid results.

---

## Decision
We enforce **Immutable Repository Snapshots**:
- Ingestion resolves the target branch or tag to a specific, immutable **40-character Git Commit SHA**.
- The repository is cloned into a dedicated directory keyed by repository ID and commit SHA:
  `/var/data/snapshots/{repo_id}/{commit_sha}/`
- Once cloned, the snapshot directory's filesystem permissions are set to read-only (`0555` / `chmod -R a-w`).
- A SHA-256 tree hash is calculated and stored in the `repository_snapshots` PostgreSQL table alongside the commit SHA.
- When sandboxes are spawned, the snapshot directory is mounted as a **strictly read-only volume (`:ro`)**. Any writable scratch directories (e.g. build directories, temporary files) are mounted as isolated, memory-backed `tmpfs` mounts.
- Evaluators and analyzers read exclusively from this immutable snapshot.

---

## Alternatives Considered
1. **Dynamic In-Place Git Checkout on Working Branch**:
   - Running directly on `origin/main` without locking commit SHAs.
   - *Rejected*: A push to `main` mid-evaluation causes inconsistent state between static analysis and runtime testing.
2. **Compressing Snapshots to Zip / Tar Archives for Every Tool**:
   - *Rejected*: Inefficient disk I/O; tools like Tree-sitter and Semgrep perform significantly faster when navigating directory structures directly.

---

## Consequences
- **Positive**:
  - 100% reproducible evaluations: Historical reports map to exact immutable commit SHAs.
  - Immune to sandbox tampering: Hostile code inside the container cannot modify source files or tamper with subsequent evaluation stages.
  - Cache reusability: Multiple evaluations of the same commit SHA can reuse the verified snapshot without re-cloning.
- **Negative**:
  - Requires disk storage management: Snapshots are cached for 24 hours, requiring a periodic garbage collector to purge stale directories.

---

## Security Impact
- Prevents time-of-check to time-of-use (TOCTOU) exploits where build scripts modify source code after static security scans complete.

---

## Operational Impact
- Deterministic, predictable filesystem storage footprint managed by automated LRU retention policies.
