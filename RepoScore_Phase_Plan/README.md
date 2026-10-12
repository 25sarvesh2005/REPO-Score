# RepoScore Phase Plan

This pack contains one Markdown phase contract for each phase 00–18, plus a reusable CI/Git-history backtracking prompt.

## Contents
- `phases/00_*.md` through `phases/18_*.md`: ordered phase instructions.
- `CI_BACKTRACKING_AGENT_PROMPT.md`: prompt for commit-aware CI, regression detection, historical inspection, and safe recovery.
- `PHASE_INDEX.md`: phase order and required commit messages.

## Workflow
1. Establish `AGENTS.md` as the project constitution.
2. Execute one phase at a time.
3. Read all previous phases and reports before starting a new phase.
4. Inspect Git history and run regression tests before edits.
5. Repair earlier-phase regressions before implementing new work.
6. Implement only the active phase, test, report, review the diff, and commit.
7. Never use destructive Git recovery automatically.

Keep the already established detailed `00_ARCHITECTURE.md` and `01_REQUIREMENTS.md` as source-of-truth documents. These phase files are execution contracts; link to detailed docs instead of replacing richer content.
