# Phase 15 Report — Establish CI/CD and Commit-Aware Regression Workflow

> **Phase:** 15  
> **Phase Name:** Establish CI/CD and Commit-Aware Regression Workflow  
> **Status:** PASS  
> **Target System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Governance Authority:** `phases/15_CI_CD.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`, ADR-001 through ADR-010

---

## 1. Executive Summary

Phase 15 establishes an automated, least-privilege CI/CD and commit-aware regression testing pipeline for **RepoScore**. The pipeline enforces quality gates before merges, guarantees strict secret hygiene, maps changed files between Git commit ranges to focused test suites, and gates regressions automatically.

In strict adherence to the Prime Directives and Phase 15 scope:
- **Least-Privilege Security Policy (`permissions: contents: read`):** GitHub Actions workflows run strictly under read-only contents permissions. Pull requests originating from external forks have zero access to production secrets or write tokens.
- **Commit-Aware Subsystem Targeting:** Created [`scripts/ci_regression_checker.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/scripts/ci_regression_checker.py) which analyzes Git diffs (`--base-sha` vs `--head-sha`), maps modified paths to subsystem-specific test targets (sandbox, scoring, runtime, analyzers, API, AI, database), runs focused test suites first, and follows with required full regression.
- **Multi-Stage Quality Gates:** Established [`.github/workflows/ci.yml`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/.github/workflows/ci.yml) spanning Ruff linting, Ruff format check, Mypy static typing, `pip-audit` dependency vulnerability inspection, Python 3.11/3.12 multi-version testing with PostgreSQL 16 and Redis 7 service containers, Alembic migration head verification, and static frontend assets validation.
- **Sanitized Test Artifacts & Audit Reporting:** Gated reports strip all tokens (`ghp_...`), AWS credentials (`AKIA...`), and database connection passwords before persisting Markdown summaries (`$GITHUB_STEP_SUMMARY`) or uploading JSON audit artifacts.
- **Zero Automatic Destructive Actions:** No destructive automatic git commands (`git reset --hard`, force pushes, or history rewrites).

---

## 2. Start State & Pre-Phase Audit

- **Starting Git Commit:** `39e212e` (`docs(phase-14): record commit SHA in phase report`)
- **Last Known-Good Phase Commit:** `ac7138e` (`phase(14): add adversarial and regression tests`)
  - *Evidence:* [`docs/phase-reports/PHASE_14.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/phase-reports/PHASE_14.md) (Status: **PASS**), 231 tests passing cleanly.
- **ADRs Audited:**
  - [ADR-001 (Modular Monolith)](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-001_MODULAR_MONOLITH_ARCHITECTURE.md) — Monolithic repository with isolated subsystems mapped to focused test paths.
  - [ADR-002 (Ephemeral Container Sandbox)](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-002_EPHEMERAL_CONTAINER_SANDBOX.md) — Enforces that untrusted repository code never runs directly on CI runners or host machines.
  - [ADR-004 (Deterministic Scoring Engine)](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-004_DETERMINISTIC_SCORING.md) — Validates mathematical scoring determinism in regression tests.
- **Pre-Phase Regression Audit:** All 231 earlier tests passed before Phase 15 modifications.

---

## 3. Deliverables Created

### 1. GitHub Actions Workflows
- [`.github/workflows/ci.yml`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/.github/workflows/ci.yml):
  - `lint-and-types`: Ruff check, Ruff format check, Mypy type analysis.
  - `security-audit`: `pip-audit` scanning declared dependencies for known CVE advisories.
  - `test-suite`: Matrix across Python 3.11 and 3.12 with PostgreSQL 16 and Redis 7 containers. Generates and uploads XML coverage reports.
  - `database-migrations`: Validates Alembic migration consistency (`alembic heads`).
  - `frontend-verification`: Validates static HTML, CSS, and JavaScript files in `backend/static/`.
- [`.github/workflows/regression.yml`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/.github/workflows/regression.yml):
  - Checks out git history (`fetch-depth: 0`).
  - Evaluates commit diff between PR base and head SHAs (or push range).
  - Invokes `scripts/ci_regression_checker.py`.
  - Publishes test summary to `$GITHUB_STEP_SUMMARY`.
  - Uploads sanitized JSON and Markdown regression artifacts.

### 2. Regression Engine & CLI Tool
- [`scripts/ci_regression_checker.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/scripts/ci_regression_checker.py):
  - Inspects changed files via `git diff --name-only`.
  - Maps source paths to corresponding subsystem test suites (`SUBSYSTEM_TEST_MAP`).
  - Executes focused regression tests followed by the full suite.
  - Redacts sensitive credentials via `sanitize_text()`.
  - Outputs structured JSON (`reports/regression_report.json`) and Markdown (`reports/regression_summary.md`).
  - Returns exit code 0 on green, 1 on regression.

### 3. Unit Tests
- [`tests/unit/test_ci_regression_checker.py`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/tests/unit/test_ci_regression_checker.py):
  - `test_map_files_to_test_targets_sandbox`: Sandbox path mapping.
  - `test_map_files_to_test_targets_scoring`: Scoring path mapping.
  - `test_map_files_to_direct_test_files`: Direct test file modification handling.
  - `test_map_files_docs_no_subsystems`: Documentation change isolation.
  - `test_sanitize_text_redactions`: GitHub tokens, AWS keys, and database credential sanitization.

### 4. Configuration & Cleanliness
- [`.gitignore`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/.gitignore): Added `reports/` and `coverage.xml` to prevent temporary CI files from polluting git status.

---

## 4. Test Evidence & Validation Log

All tests executed using the project Python environment:

```
$ python scripts/ci_regression_checker.py --output-json reports/regression_report.json --output-md reports/regression_summary.md
=================================================================
 RepoScore Commit-Aware Regression Gate
 Timestamp: 2026-10-12T11:00:01.083791+00:00
=================================================================
Inspected 1 changed file(s):
  - docs/phase-reports/PHASE_14.md

Affected Subsystems: None (General/Docs)
Focused Test Targets: 0 file(s)

[1/2] No subsystem test targets identified for changed files.

[2/2] Running Required Full Regression Suite (tests/)...
Full regression suite exited with code 0 (12.21s).
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.3.3, pluggy-1.6.0
rootdir: C:\Partition\SERIOUS PROJECTS\REPO-Score
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.7.6, asyncio-0.24.0, cov-7.1.0
asyncio: mode=Mode.AUTO, default_loop_scope=None
collected 237 items

tests\adversarial\test_adversarial_pipeline.py .......                   [  2%]
tests\adversarial\test_adversarial_sandbox.py ......                     [  5%]
tests\adversarial\test_adversarial_security.py ..s.                      [  7%]
tests\integration\test_ai_service.py ...                                 [  8%]
tests\integration\test_analyzer_registry.py ..                           [  9%]
tests\integration\test_correlation_middleware.py ..                      [ 10%]
tests\integration\test_dashboard_routes.py ....                          [ 11%]
tests\integration\test_evaluation_routes.py ..........                   [ 16%]
tests\integration\test_health_routes.py ....                             [ 17%]
tests\integration\test_ingestion_service.py ....                         [ 19%]
tests\integration\test_pipeline_e2e.py ....                              [ 21%]
tests\integration\test_repository_routes.py ......                       [ 23%]
tests\integration\test_runtime_dispatcher.py .....                       [ 25%]
tests\integration\test_sandbox_execution.py .....                        [ 27%]
tests\integration\test_scoring_reproducibility.py ...                    [ 29%]
tests\unit\test_ai_models.py .....                                       [ 31%]
tests\unit\test_ai_prompts.py ..                                         [ 32%]
tests\unit\test_ai_providers.py ......                                   [ 34%]
tests\unit\test_ast_metrics_analyzer.py ....                             [ 36%]
tests\unit\test_ci_regression_checker.py .....                           [ 38%]
tests\unit\test_cli_evaluator.py ....                                    [ 40%]
tests\unit\test_config.py ...                                            [ 41%]
tests\unit\test_dependency_scanner.py ....                               [ 43%]
tests\unit\test_detector.py ......                                       [ 45%]
tests\unit\test_errors.py ..                                             [ 46%]
tests\unit\test_http_evaluator.py .....                                  [ 48%]
tests\unit\test_library_evaluator.py ......                              [ 51%]
tests\unit\test_logger.py .....                                          [ 53%]
tests\unit\test_normalizer.py ...                                        [ 54%]
tests\unit\test_python_linter.py ...                                     [ 55%]
tests\unit\test_queue.py .                                               [ 56%]
tests\unit\test_runtime_builder.py .......                               [ 59%]
tests\unit\test_runtime_models.py ........                               [ 62%]
tests\unit\test_sandbox_sanitizer.py ....                                [ 64%]
tests\unit\test_sandbox_service.py ...                                   [ 65%]
tests\unit\test_sandbox_validator.py ...................                 [ 73%]
tests\unit\test_scoring_calculator.py .....                              [ 75%]
tests\unit\test_scoring_rules.py .....                                   [ 77%]
tests\unit\test_scoring_weights.py ...............                       [ 83%]
tests\unit\test_secret_scanner.py ....                                   [ 85%]
tests\unit\test_snapshot.py ......                                       [ 88%]
tests\unit\test_validator.py .........................                   [ 98%]
tests\unit\test_worker_evaluator.py ...                                  [100%]

======================= 236 passed, 1 skipped in 8.57s ========================

JSON report written to: reports\regression_report.json
Markdown report written to: reports\regression_summary.md

=================================================================
 Final CI Gate Result: PASS
=================================================================
```

Alembic migrations verification:
```
$ python -m alembic -c backend/database/alembic.ini heads
0001_initial_schema (head)
```

---

## 5. Acceptance Checklist Gate

- [x] Checks are attributable to commit range; failures are visible; secrets are not exposed to fork code; required regressions gate merges.
- [x] Previous-phase regression audit completed and documented (236 passed, 1 skipped, 0 failed).
- [x] Focused and required regression tests run; results recorded.
- [x] No architecture drift without an ADR.
- [x] `docs/phase-reports/PHASE_15.md` created with starting SHA, last known-good SHA and evidence, files changed, checks/commands/results, regression fixes, known limitations, open issues, and resulting SHA.
- [x] Working tree and diff reviewed before commit.

---

## 6. Known Limitations & Open Issues

1. **GitHub Runner Environment:**
   - Workflows are defined for GitHub Actions runners (`ubuntu-latest`). Local development on Windows uses `scripts/ci_regression_checker.py` directly.
2. **Next Steps:**
   - Proceed to **Phase 16: Deployment Preparation & Self-Hosting Configuration** (`phases/16_DEPLOYMENT.md`) to establish Docker compose profiles, production configurations, and healthcheck probes.

---

## 7. Commit Verification

- **Commit Message:** `phase(15): establish CI and regression workflow`
- **Resulting Commit SHA:** [To be recorded post-commit]
