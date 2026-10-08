# Observability & Telemetry Architecture

> **Document:** `OBSERVABILITY_ARCHITECTURE.md`  
> **Status:** Active / Architectural Contract  
> **Owner:** Core Architecture & DevOps Team  
> **Referenced ADRs:** ADR-001, ADR-007

---

## 1. Observability Pillars

RepoScore implements comprehensive observability across all asynchronous evaluation stages.

```mermaid
graph TD
    subgraph Client ["Client Interface"]
        UI["Next.js UI (SSE Stream Listener)"]
    end

    subgraph APILayer ["FastAPI Ingress"]
        API["API Controller\n(Assigns correlation_id)"]
    end

    subgraph Pipeline ["Asynchronous Evaluation Pipeline"]
        Queue["Redis Task Queue\n(Transmits Context)"]
        Worker["Evaluation Worker"]
        Sandbox["Docker Sandbox Engine"]
    end

    subgraph ObservabilityStack ["Observability Sinks"]
        LogSink["Structured JSON Logs\n(Secret Sanitized)"]
        PromSink["Prometheus Metrics (/metrics)"]
        EventSink["PostgreSQL Event Log\n(evaluation_events)"]
        SSESink["Real-time SSE Stream\n(/evaluations/{id}/events)"]
    end

    API -->|1. Generate correlation_id| Queue
    Queue --> Worker
    Worker --> Sandbox
    Worker --> LogSink
    Worker --> PromSink
    Worker --> EventSink
    EventSink --> SSESink
    SSESink --> UI
```

---

## 2. Distributed Tracing & Correlation

Every evaluation creates a globally unique `correlation_id` (UUIDv7) at the API ingress boundary. This identifier is propagated across all system boundaries:

```text
HTTP Request (X-Correlation-ID Header)
  ├── FastAPI Route Handler
  │     ├── PostgreSQL: evaluations.correlation_id
  │     └── Redis Task Payload: {"evaluation_id": "...", "correlation_id": "..."}
  │           └── Evaluation Worker
  │                 ├── Container Labels: reposcore.correlation_id="..."
  │                 ├── Analyzer Spans
  │                 └── AI Inference Span
```

---

## 3. Structured Logging & Secret Sanitization

All logs are emitted as single-line structured JSON objects to `stdout`.

### 3.1 Log Format Schema:
```json
{
  "timestamp": "2026-10-08T22:31:45.102Z",
  "level": "INFO",
  "correlation_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
  "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
  "component": "sandbox.runner",
  "step": "BUILDING",
  "event": "container_command_completed",
  "command": "npm run build",
  "exit_code": 0,
  "duration_ms": 4210,
  "cpu_peak_percent": 142.5,
  "memory_rss_mb": 312
}
```

### 3.2 Secret Sanitization Filter:
RepoScore evaluates third-party code that may attempt to leak environment variables or log private credentials. The logger includes an inline regex sanitization filter that intercepts and redacts:
- GitHub Personal Access Tokens (`ghp_[a-zA-Z0-9]{36}`)
- AWS Access Keys (`AKIA[0-9A-Z]{16}`)
- JWT tokens (`Bearer eyJ...`)
- Private key headers (`-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----`)
- Database connection URLs containing passwords (`postgres://user:password@host/db`)

---

## 4. Operational Metrics (Prometheus)

Exposed via `GET /metrics` on the FastAPI server:

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `reposcore_evaluations_total` | Counter | `status` (completed, failed, cancelled) | Total evaluations processed. |
| `reposcore_evaluation_duration_seconds` | Histogram | `status` | End-to-end evaluation latency distribution. |
| `reposcore_step_duration_seconds` | Histogram | `step_name`, `status` | Duration of individual evaluation steps. |
| `reposcore_active_sandboxes` | Gauge | `worker_id` | Number of active Docker sandbox containers. |
| `reposcore_queue_depth` | Gauge | `queue_name` | Pending evaluation jobs awaiting workers. |
| `reposcore_ai_inference_duration_seconds`| Histogram | `provider`, `model` | Latency of AI inference requests. |
| `reposcore_security_findings_total` | Counter | `severity`, `source` | Aggregate count of security findings discovered. |

---

## 5. Live Client Event Streaming (Server-Sent Events)

Clients track real-time progress via Server-Sent Events (`GET /evaluations/{id}/events`):

```text
event: step_started
data: {"step": "ANALYZING", "timestamp": "2026-10-08T22:30:05Z"}

event: evidence_discovered
data: {"id": "01925b4a-8d1a", "category": "SECURITY", "severity": "HIGH", "title": "Hardcoded Secret"}

event: step_completed
data: {"step": "ANALYZING", "duration_ms": 3200, "status": "SUCCESS"}

event: evaluation_completed
data: {"evaluation_id": "01925b4a-8cf2", "overall_score": 84.6, "status": "COMPLETED"}
```
