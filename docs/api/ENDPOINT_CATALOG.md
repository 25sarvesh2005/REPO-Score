# REST API Endpoint Catalog & Interface Contract

> **Document:** `ENDPOINT_CATALOG.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / API Contract Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. API Architecture & Design Principles

The RepoScore API layer is designed as a stateless, asynchronous gateway conforming to **RESTful conventions** and **OpenAPI 3.1**:
1. **Asynchronous Hand-off:** Compute-heavy evaluations return `HTTP 202 Accepted` immediately, enqueuing tasks to Redis and returning status tracking endpoints.
2. **Versioned Routes:** All operational endpoints reside under the `/api/v1/` prefix.
3. **Traceability:** Every incoming request requires or generates a distributed `correlation_id` returned in the `X-Correlation-ID` response header.
4. **Structured RFC 7807 Errors:** All error responses conform to `application/problem+json`.
5. **Deterministic Data Separation:** Numerical scores and empirical evidence are exposed separately from qualitative AI summaries.

---

## 2. Standard Headers & Error Envelope

### 2.1 Standard Request & Response Headers
| Header Name | Type | Direction | Description |
|---|---|---|---|
| `X-Correlation-ID` | UUIDv7 | In / Out | Distributed tracing identifier; generated automatically if omitted by client. |
| `Idempotency-Key` | String (UUID) | In | Client-provided key for `POST /api/v1/evaluations` to prevent duplicate task dispatch. |
| `Content-Type` | String | In / Out | `application/json` (or `text/event-stream` for SSE). |
| `Location` | URI | Out | URI pointing to status tracking resource upon `201` or `202` response. |
| `X-RateLimit-Limit` | Integer | Out | Permitted request quota per minute window. |
| `X-RateLimit-Remaining`| Integer | Out | Remaining requests in active window. |

### 2.2 Standard Error Envelope (RFC 7807 Problem Details)
```json
{
  "type": "https://reposcore.internal/errors/resource-not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Evaluation with ID '01925b4a-8cf2-7612-882f-3d18c9ba1100' was not found.",
  "instance": "/api/v1/evaluations/01925b4a-8cf2-7612-882f-3d18c9ba1100",
  "correlation_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
  "timestamp": "2026-10-12T14:30:00Z",
  "invalid_params": []
}
```

---

## 3. Endpoint Specifications

### 3.1 Repository Management

#### `POST /api/v1/repositories`
- **Summary:** Register or Ingest Repository
- **Description:** Validates GitHub URL, queries repository metadata, creates the repository record, and detects default branch.
- **Request Body (`application/json`):**
  ```json
  {
    "url": "https://github.com/fastapi/fastapi",
    "provider": "github"
  }
  ```
- **Responses:**
  - `201 Created`: Repository registered successfully.
    ```json
    {
      "id": "01925b4a-1000-7000-8000-000000000001",
      "url": "https://github.com/fastapi/fastapi",
      "owner": "fastapi",
      "name": "fastapi",
      "default_branch": "master",
      "is_private": false,
      "stars_count": 78200,
      "primary_language": "Python",
      "created_at": "2026-10-12T14:00:00Z"
    }
    ```
  - `400 Bad Request`: Malformed GitHub URL.
  - `404 Not Found`: Repository does not exist or is inaccessible.
  - `422 Unprocessable Entity`: Validation failure on input schema.

#### `GET /api/v1/repositories/{id}`
- **Summary:** Retrieve Repository Details
- **Description:** Returns repository metadata and a list of registered immutable snapshots.
- **Path Parameters:** `id` (UUID)
- **Responses:**
  - `200 OK`: Returns repository details and snapshot summaries.
  - `404 Not Found`: Repository ID does not exist.

---

### 3.2 Evaluation Orchestration

#### `POST /api/v1/evaluations`
- **Summary:** Enqueue Evaluation Job
- **Description:** Enqueues an asynchronous evaluation job against a repository. Resolves target ref, creates snapshot record, and pushes a task to Redis.
- **Headers:** Optional `Idempotency-Key` (UUID)
- **Request Body (`application/json`):**
  ```json
  {
    "repository_id": "01925b4a-1000-7000-8000-000000000001",
    "ref": "main",
    "options": {
      "timeout_seconds": 600,
      "enable_ai_reasoning": true
    }
  }
  ```
- **Responses:**
  - `202 Accepted`: Job queued successfully.
    ```json
    {
      "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
      "status": "QUEUED",
      "correlation_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
      "status_url": "/api/v1/evaluations/01925b4a-8cf2-7612-882f-3d18c9ba1100/status",
      "events_url": "/api/v1/evaluations/01925b4a-8cf2-7612-882f-3d18c9ba1100/events"
    }
    ```
  - `400 Bad Request`: Invalid options or unsupported configuration.
  - `404 Not Found`: Referenced repository does not exist.

#### `GET /api/v1/evaluations/{id}`
- **Summary:** Get Master Evaluation Record
- **Description:** Returns the complete evaluation metadata, target commit SHA, snapshot identity, status, timing, and error summary.
- **Responses:** `200 OK`, `404 Not Found`.

#### `GET /api/v1/evaluations/{id}/status`
- **Summary:** Lightweight Evaluation Status Polling
- **Description:** High-frequency, low-latency endpoint returning current lifecycle stage, active step name, duration, and completion status.
- **Responses:**
  - `200 OK`:
    ```json
    {
      "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
      "status": "BUILDING",
      "current_step": "compiling_application",
      "elapsed_seconds": 45,
      "is_terminal": false
    }
    ```

#### `GET /api/v1/evaluations/{id}/events`
- **Summary:** Real-Time Lifecycle Event Stream (SSE)
- **Description:** Unidirectional Server-Sent Events stream delivering state transitions, step progress, and log chunks.
- **Headers:** `Accept: text/event-stream`
- **Response (`text/event-stream`):**
  ```text
  event: step_progress
  data: {"step":"BUILDING","progress_percent":60,"message":"Compiling dependencies..."}

  event: state_transition
  data: {"from_status":"BUILDING","to_status":"STARTING"}
  ```

#### `POST /api/v1/evaluations/{id}/cancel`
- **Summary:** Cancel Active Evaluation
- **Description:** Dispatches an abort signal to worker processes, terminating sandbox containers immediately and transitioning status to `CANCELLED`.
- **Responses:**
  - `200 OK`:
    ```json
    {
      "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
      "status": "CANCELLED",
      "message": "Cancellation signal dispatched to worker."
    }
    ```
  - `400 Bad Request`: Evaluation is already in a terminal state.

---

### 3.3 Scorecard & Results Exploration

#### `GET /api/v1/evaluations/{id}/score`
- **Summary:** Get Finalized Deterministic Scorecard
- **Description:** Retrieves overall composite score (0-100), letter grade, ruleset version, and all 10 dimension breakdowns with itemized receipts.
- **Responses:**
  - `200 OK`:
    ```json
    {
      "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
      "scoring_version": "1.0.0",
      "overall_score": 88.5,
      "grade": "A",
      "dimensions": [
        {
          "dimension_name": "Security",
          "score": 90.0,
          "weight": 0.16,
          "itemized_receipt": [
            {
              "type": "DEDUCTION",
              "rule_code": "RULE_MEDIUM_CVE",
              "evidence_id": "01925b4a-e011-7000-8000-000000000001",
              "description": "Medium CVE-2023-1234 in dependency",
              "points_deducted": 10.0
            }
          ]
        }
      ],
      "ai_executive_summary": "High-quality Python service with strong test coverage...",
      "created_at": "2026-10-12T14:35:00Z"
    }
    ```
  - `404 Not Found`: Evaluation not found.
  - `409 Conflict`: Evaluation is still running; score not finalized yet.

#### `GET /api/v1/evaluations/{id}/evidence`
- **Summary:** Paginated Normalized Evidence Explorer
- **Description:** Retrieves paginated evidence items with category and severity filtering.
- **Query Parameters:**
  - `category` (optional enum): `SECURITY`, `CORRECTNESS`, `PERFORMANCE`, etc.
  - `severity` (optional enum): `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`.
  - `limit` (optional integer): Default 50, max 200.
  - `offset` (optional integer): Default 0.
- **Responses:**
  - `200 OK`:
    ```json
    {
      "items": [
        {
          "id": "01925b4a-e011-7000-8000-000000000001",
          "source": "semgrep",
          "category": "SECURITY",
          "severity": "HIGH",
          "confidence": 0.95,
          "title": "SQL Injection Pattern Detected",
          "description": "Unsanitized user input formatted into SQL query string.",
          "location": {
            "file_path": "backend/db.py",
            "start_line": 28,
            "end_line": 30
          }
        }
      ],
      "total_count": 1,
      "limit": 50,
      "offset": 0,
      "has_more": false
    }
    ```

#### `GET /api/v1/evaluations/{id}/runtime`
- **Summary:** Runtime Telemetry & Probing Telemetry
- **Description:** Exposes startup duration, HTTP probe latency percentiles, cgroups memory RSS, CPU usage, and process exit codes.
- **Responses:** `200 OK`, `404 Not Found`.

#### `GET /api/v1/evaluations/{id}/security`
- **Summary:** Security & Vulnerability Report
- **Description:** Curated security audit: CVE dependencies (OSV), hardcoded secrets, and OWASP rule violations.
- **Responses:** `200 OK`, `404 Not Found`.

#### `GET /api/v1/evaluations/{id}/findings`
- **Summary:** Static Findings Explorer
- **Description:** Lists raw AST and linter findings across Tree-sitter, Semgrep, and Ruff.
- **Responses:** `200 OK`, `404 Not Found`.

#### `GET /api/v1/evaluations/{id}/history`
- **Summary:** Historical Evaluation Trend Comparison
- **Description:** Compares recent evaluations across commit SHAs for the same repository to show score regressions and fixed vulnerabilities.
- **Query Parameters:** `limit` (default 10, max 50).
- **Responses:** `200 OK`.

---

### 3.4 Operational & Health Probes

#### `GET /health`
- **Summary:** Gateway Liveness Probe
- **Description:** Verifies that the FastAPI process is alive and accepting traffic.
- **Responses:** `200 OK` (`{"status": "healthy"}`)

#### `GET /ready`
- **Summary:** Gateway Readiness Probe
- **Description:** Verifies downstream connectivity to PostgreSQL and Redis.
- **Responses:**
  - `200 OK`:
    ```json
    {
      "status": "ready",
      "database": "connected",
      "redis": "connected"
    }
    ```
  - `503 Service Unavailable`: One or more backing services are unreachable.
