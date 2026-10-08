# ADR-001: Modular Monolith Architecture

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Core Architecture Team  
> **Consulted:** Systems, Security, and Product Leads  

---

## Context
When designing RepoScore, an autonomous repository evaluation platform comprising ingestion, static analysis, sandboxing, scoring, and AI synthesis, an early architectural fork was whether to build as a distributed microservices network (separate services for Ingestion, Static Analysis, Sandbox Runner, Scoring, AI) or as a unified modular monolith with isolated background workers.

Microservices introduce distributed tracing complexity, inter-service network serialization latency, independent failure modes, complicated local development setups, and higher operational overhead.

---

## Decision
We choose a **modular monolith backend** with **asynchronous worker execution**.
- The codebase is structured as a single cohesive Python project where each domain (`api`, `repository`, `orchestration`, `sandbox`, `analyzers`, `runtime`, `evidence`, `scoring`, `ai`, `database`) is an isolated module with strict public boundaries and typed interfaces.
- High-latency workloads (cloning, building, executing sandboxes, scanning) are executed by stateless worker processes consuming tasks from a shared Redis queue.
- Inter-module communication within a process occurs via direct, typed Python protocols rather than internal HTTP or gRPC calls.

---

## Alternatives Considered
1. **Full Microservices Architecture**:
   - *Pros*: Independent deployment cadence per analyzer; polyglot language freedom.
   - *Cons*: Massive overhead in local developer setup, high latency serializing large ASTs/snapshots across network boundaries, complex distributed transactions, expensive CI/CD.
2. **Serverless Functions (FaaS)**:
   - *Pros*: Auto-scaling execution.
   - *Cons*: Rigid execution time ceilings (15 min), lacks Docker-in-Docker / cgroups sandbox capabilities, heavy cold start penalties.

---

## Consequences
- **Positive**:
  - Trivial local setup: developers can run the entire system with `docker compose up` or local Python virtual environment.
  - Zero network serialization overhead for internal domain interfaces.
  - Consistent transactional guarantees through shared PostgreSQL database.
  - Clear refactoring path: if any module (e.g. Sandbox Runner) demands standalone horizontal scaling, its interface can be extracted into an independent service without restructuring caller logic.
- **Negative**:
  - Requires continuous enforcement of module boundaries to prevent spaghetti import coupling (monitored via linting rules).

---

## Security Impact
- Reduced attack surface: No unauthenticated inter-service network hops or internal service mesh credentials required.
- Single unified authentication and authorization boundary at the API gateway layer.

---

## Operational Impact
- Drastically simpler deployment: Only two primary backend application targets exist (API process and Worker process).
- Unified logging, shared connection pools, and single database migration timeline.
