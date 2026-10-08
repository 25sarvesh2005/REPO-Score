# ADR-009: Runtime Evaluator Strategy Architecture

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Core Systems Architecture Team  
> **Consulted:** DevOps & Evaluation Leads  

---

## Context
Repositories across GitHub represent diverse application models: REST APIs, CLI tools, reusable SDKs/libraries, background daemons, or frontend web applications. A single uniform runtime test strategy (e.g. attempting to curl an HTTP port) would fail when analyzing a command-line utility or a pure algorithmic library.

We need a flexible, extensible runtime execution strategy that adapts dynamically to the repository's architectural archetype while collecting standardized behavioral observations.

---

## Decision
We implement a **Strategy-Based Runtime Evaluator Architecture**:
- An inspection phase analyzes repository manifest files, entry points, and dependencies to detect the application archetype:
  - `HTTP_API`: Web services exposing REST or GraphQL endpoints.
  - `CLI_APPLICATION`: Standalone executables accepting terminal flags and arguments.
  - `LIBRARY`: Reusable software packages containing test suites.
  - `WORKER`: Long-running event/job processors.
- A strategy resolver selects the corresponding `IRuntimeEvaluator` implementation:
  - `HttpApiEvaluator`: Boots service in sandbox, verifies socket listening, probes canonical endpoints (`/health`, `/`), runs synthetic concurrent HTTP load, measures latency percentiles, tests graceful SIGTERM shutdown.
  - `CliEvaluator`: Invokes `--help`, `--version`, tests invalid arguments for proper error exits, tests JSON output flags.
  - `LibraryEvaluator`: Dispatches native test runners (`pytest`, `npm test`, `cargo test`), parses test reports, extracts code coverage.
  - `WorkerEvaluator`: Verifies startup stability and clean signal handling.
- All evaluators yield a normalized `RuntimeObservation` record detailing startup time, exit codes, resource utilization (cgroups CPU/RAM), and captured stack traces.

---

## Alternatives Considered
1. **HTTP-Only Assumption**:
   - Assuming all projects run an HTTP web server on port 8000/3000.
   - *Rejected*: Inaccurate for the majority of open-source libraries and CLI tools.
2. **Execute Custom User Scripts Directly**:
   - Trusting a `.reposcore.yml` file supplied by the repository to define build and run commands.
   - *Rejected*: Direct security violation. Malicious repositories could configure benign scripts during evaluation to mask malicious payloads or attack the host.

---

## Consequences
- **Positive**:
  - Broad evaluation coverage across disparate software genres.
  - Evaluates applications based on their natural usage patterns.
  - Standardized observation schema enables fair, comparable scoring across different project types.
- **Negative**:
  - Requires maintaining specialized probe logic for each supported application archetype.

---

## Security Impact
- All execution strategies run exclusively inside ephemeral, capability-stripped Docker containers with disabled or proxied networking.

---

## Operational Impact
- Granular timeouts and watchdog timers guarantee that hung applications or infinite loops are terminated cleanly within 30–60 seconds.
