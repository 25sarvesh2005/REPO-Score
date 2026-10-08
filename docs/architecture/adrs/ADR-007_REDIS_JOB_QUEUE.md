# ADR-007: Redis Distributed Job Queue & Pub/Sub

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** Distributed Systems & Core Architecture Team  
> **Consulted:** DevOps Leads  

---

## Context
Repository evaluation involves long-running, CPU-intensive operations (cloning git trees, running static scans, compiling binaries in Docker containers, executing runtime probes). These cannot execute synchronously inside the FastAPI request/response lifecycle without causing client timeouts and exhausting server worker threads. We need an asynchronous task distribution and live progress streaming mechanism.

---

## Decision
We select **Redis 7+** as the central message broker, task queue, and pub/sub engine:
- Asynchronous task distribution: API nodes enqueue evaluation tasks to Redis streams/lists (`reposcore:queue:evaluations`), and stateless background workers consume tasks with deterministic acknowledgment semantics.
- Real-time progress broadcasting: Workers publish stage transitions and evidence discoveries to Redis Pub/Sub channels (`reposcore:events:{evaluation_id}`), which the API layer bridges directly to clients via Server-Sent Events (SSE).
- Heartbeat tracking and distributed locking: Active workers register heartbeats with TTLs (`reposcore:worker:heartbeat:{worker_id}`) to detect worker crashes and reclaim orphaned tasks.

---

## Alternatives Considered
1. **RabbitMQ / AMQP**:
   - *Pros*: Advanced message routing and acknowledgement topologies.
   - *Cons*: Additional Erlang runtime overhead, higher configuration complexity for local developer environments compared to Redis.
2. **PostgreSQL LISTEN / NOTIFY**:
   - *Pros*: Zero additional infrastructure beyond Postgres.
   - *Cons*: Can cause database bloat under heavy pub/sub event volume; lacks mature queue retry/rate-limiting abstractions.
3. **Kafka**:
   - *Rejected*: Massive operational overkill for task orchestration; unsuitable for lightweight local developer environments.

---

## Consequences
- **Positive**:
  - Extremely fast, sub-millisecond queuing latency.
  - Combines task queuing, pub/sub event streaming, and distributed locks within a single lightweight service.
  - Trivial local Docker Compose deployment.
- **Negative**:
  - In-memory nature requires enabling Redis Append-Only File (AOF) persistence to prevent job loss across broker restarts.

---

## Security Impact
- Redis is isolated within an internal backend Docker network and configured with mandatory authentication passwords.
- No public exposure of Redis ports.

---

## Operational Impact
- Negligible CPU footprint; predictable memory consumption bounded by max queue length configurations.
