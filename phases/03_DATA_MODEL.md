# Phase 03 — Data model and persistence design

**Project:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
**Previous phase:** Phase 02  
**Next phase:** Phase 04  
**Scope:** Schema design; implementation only if explicitly authorized  
**Required commit:** `phase(03): define persistence data model`

## Objective

Data model and persistence design. Preserve the core rule: **evidence is the source of truth; AI interpretation is advisory.**

## Mandatory startup protocol

1. Read `/AGENTS.md`.
2. Read all previous phase files, their `docs/phase-reports/PHASE_XX.md` reports, relevant requirements, architecture docs, security docs, and ADRs.
3. Inspect `git status --short --branch`, `git log --oneline --decorate --graph -30`, `git diff --check`, and the current branch/base SHA.
4. Identify the last known-good commit using actual CI/test evidence; never assume an older commit is good merely because it is older.
5. Run the existing relevant tests before editing and preserve their output.
6. If a previous-phase regression exists, STOP new-phase work. Reproduce it, inspect the introducing commit range, repair it with the smallest safe change, add a regression test, rerun tests, and document it before continuing.
7. Never discard user changes, rewrite shared history, or execute untrusted repository code directly on the host.

## Phase work

Define Repository, RepositorySnapshot, Evaluation, EvaluationStep, ExecutionEnvironment, TestScenario, RuntimeObservation, StaticFinding, SecurityFinding, Evidence, Score, ScoreDimension, Recommendation, AIAnalysis, and EvaluationEvent. Specify relations, constraints, indexes, lifecycle, retention, immutable fields, and migrations.

## Non-negotiable constraints

- Implement only this phase's scope; preserve earlier phase contracts.
- No fake implementations, placeholder success, fabricated test results, fabricated evidence, or invented commit SHAs.
- Untrusted repository code must execute only inside the approved sandbox.
- Never expose secrets in logs, prompts, CI artifacts, or test output.
- Scoring must be deterministic and versioned; AI cannot override the authoritative score.
- Use explicit failure states, bounded retries, timeouts, and cleanup.
- Keep paid providers optional and prefer free/open-source tools.
- Any architecture change requires a reviewed ADR.

## Validation gate

1. Run focused tests for changed components.
2. Run regression tests for all affected earlier phases.
3. Run configured formatting, lint, type, security, migration, integration, and end-to-end checks as applicable.
4. Inspect real exit codes and logs; do not rely only on a coding agent's summary.
5. Run `git diff --check`, review the complete diff, and verify no secrets or unrelated files were introduced.
6. If any required check fails, fix or explicitly block the phase; do not skip tests to manufacture success.

## Acceptance gate

- [ ] Data lineage and snapshot immutability are preserved; relationships and migration strategy documented; integrity tests planned or implemented per scope.
- [ ] Previous-phase regression audit completed and documented.
- [ ] Focused and required regression tests run; results recorded.
- [ ] No architecture drift without an ADR.
- [ ] `docs/phase-reports/PHASE_03.md` created with starting SHA, last known-good SHA and evidence, files changed, checks/commands/results, regression fixes, known limitations, open issues, and resulting SHA.
- [ ] Working tree and diff reviewed before commit.

## Commit procedure

```bash
git status
git diff --check
git diff
git add <intended-files>
git commit -m "phase(03): define persistence data model"
git status
git log -1 --oneline
```

Do not use `git reset --hard`, force-push, or rewrite shared history as automatic recovery. Prefer a reviewed corrective commit or `git revert`. Do not commit unrelated or unknown user changes.

## Handoff

The next phase is **Phase 04**. The next agent must read this phase report, inspect the actual commit, and rerun relevant tests before proceeding.
