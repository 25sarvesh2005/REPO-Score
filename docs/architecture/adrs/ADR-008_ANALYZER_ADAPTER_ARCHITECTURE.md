# ADR-008: Analyzer Adapter Architecture

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Core Architecture Team  
> **Consulted:** Tooling & Security Leads  

---

## Context
Static analysis requires integrating a wide variety of tools: syntax trees (Tree-sitter), security rules (Semgrep), language linters (Ruff, ESLint, Bandit), and vulnerability scanners (OSV). Directly coupling the core evaluation pipeline to individual tool CLIs or library APIs would create brittle code, make testing difficult, and prevent adding new languages or analyzers in the future.

---

## Decision
We establish a **Pluggable Analyzer Adapter Architecture**:
- All analysis tools implement a common `BaseAnalyzer` Python abstract interface.
- Each adapter defines its metadata: `name`, `version`, `category`, `target_languages`, and implements `can_analyze(tech_stack) -> bool` and `analyze(snapshot_path, context) -> list[StaticFinding]`.
- An `AnalyzerRegistry` dynamically discovers, instantiates, and executes relevant adapters in parallel using `asyncio.gather`.
- The evaluation orchestrator interacts solely with `BaseAnalyzer` interfaces and knows nothing about the underlying tool CLI flags, configuration formats, or internal execution mechanisms.
- Disparate analyzer outputs are converted into normalized `StaticFinding` models before reaching the Evidence Engine.

---

## Alternatives Considered
1. **Monolithic Multi-Tool Scanner Script**:
   - A single monolithic shell or Python script that runs all tools in sequence.
   - *Rejected*: Impossible to test individual tools in isolation, brittle error handling (one failure aborts everything), zero parallelization.
2. **Third-Party Meta-Analyzer Framework (e.g. Mega-Linter)**:
   - *Rejected*: Massive container images (15GB+), slow execution, high resource consumption, lack of fine-grained structured evidence integration.

---

## Consequences
- **Positive**:
  - Open for extension, closed for modification: Adding a new language analyzer (e.g., Go, Rust, Java) requires only writing a new self-contained adapter class.
  - Fail-safe isolation: If an individual analyzer encounters an unparseable file or crashes, other analyzers continue unaffected.
  - Testability: Adapters can be mocked with 100% test coverage using fixed file fixtures.
- **Negative**:
  - Requires maintaining adapter compatibility as underlying tool CLIs update their output schemas.

---

## Security Impact
- Adapters execute tools with read-only access to repository snapshots and zero network access.

---

## Operational Impact
- Fast parallel analysis: Running Tree-sitter, Ruff, and Semgrep concurrently finishes in seconds rather than serial accumulation.
