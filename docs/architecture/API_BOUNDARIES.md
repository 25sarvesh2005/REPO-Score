# API Boundaries & Interface Contracts

> **Document:** `API_BOUNDARIES.md`  
> **Status:** Active / Architectural Contract  
> **Owner:** API Engineering Team  
> **Referenced ADRs:** ADR-001, ADR-007

---

## 1. API Design Principles & Boundaries

The RepoScore API Layer is built with **FastAPI** and **Pydantic v2**:
1. **Stateless Gateway**: The API server handles request validation, authentication, rate limiting, and persistence queries. It **never** executes untrusted repository code directly.
2. **Strict Typing**: All request payloads and response bodies adhere to typed Pydantic models with OpenAPI 3.1 documentation.
3. **Structured Errors**: Failures return standard RFC 7807 Problem Details schemas.
4. **Asynchronous Hand-off**: Submissions enqueue tasks to Redis and return HTTP `202 Accepted` with location headers pointing to evaluation status.

---

## 2. Endpoint Catalog & Specifications

### 2.1 Repository Management

#### `POST /repositories`
- **Description**: Registers a repository, validates accessibility, fetches Git metadata, and initiates ingestion.
- **Request**:
  ```json
  {
    "url": "https://github.com/fastapi/fastapi",
    "provider": "github"
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "id": "01925b4a-1000-7000-8000-000000000001",
    "url": "https://github.com/fastapi/fastapi",
    "owner": "fastapi",
    "name": "fastapi",
    "default_branch": "master",
    "created_at": "2026-10-08T22:30:00Z"
  }
  ```

#### `GET /repositories/{id}`
- **Description**: Returns repository metadata, tracked branches, and snapshots.
- **Response**: `200 OK`

---

### 2.2 Evaluation Orchestration

#### `POST /evaluations`
- **Description**: Enqueues an evaluation pipeline job against a repository snapshot.
- **Request**:
  ```json
  {
    "repository_id": "01925b4a-1000-7000-8000-000000000001",
    "ref": "master",
    "options": {
      "timeout_seconds": 600,
      "enable_ai_reasoning": true
    }
  }
  ```
- **Response**: `202 Accepted`
  ```json
  {
    "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
    "status": "QUEUED",
    "correlation_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
    "status_url": "/evaluations/01925b4a-8cf2-7612-882f-3d18c9ba1100/status"
  }
  ```

#### `POST /evaluations/{id}/cancel`
- **Description**: Issues an abort signal to terminate active sandbox processes and mark the evaluation cancelled.
- **Response**: `200 OK`
  ```json
  {
    "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
    "status": "CANCELLED",
    "message": "Cancellation request dispatched to active workers."
  }
  ```

#### `GET /evaluations/{id}/status`
- **Description**: High-frequency, lightweight polling endpoint returning current lifecycle state and step status.
- **Response**: `200 OK`
  ```json
  {
    "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
    "status": "BUILDING",
    "current_step": "compiling_application",
    "elapsed_seconds": 45
  }
  ```

#### `GET /evaluations/{id}/events`
- **Description**: Server-Sent Events (SSE) streaming endpoint delivering real-time lifecycle transitions and evidence discoveries.
- **Response Headers**: `Content-Type: text/event-stream`, `Cache-Control: no-cache`

---

### 2.3 Evaluation Results & Evidence Exploration

#### `GET /evaluations/{id}/score`
- **Description**: Retrieves the finalized deterministic scorecard, including composite score, letter grade, and 10 dimension receipts.
- **Response**: `200 OK`

#### `GET /evaluations/{id}/evidence`
- **Description**: Paginated list of normalized evidence items with category, severity, and confidence filtering.
- **Query Params**: `category=SECURITY&severity=CRITICAL&limit=50&offset=0`
- **Response**: `200 OK`

#### `GET /evaluations/{id}/runtime`
- **Description**: Detailed runtime evaluation telemetry: startup duration, probe results, HTTP latency percentiles, cgroups resource metrics (CPU/RAM), and exit codes.
- **Response**: `200 OK`

#### `GET /evaluations/{id}/security`
- **Description**: Curated security findings: CVE dependencies (OSV), hardcoded secret discoveries, and OWASP rule violations.
- **Response**: `200 OK`

#### `GET /evaluations/{id}/history`
- **Description**: Historical evaluation comparisons across recent commit SHAs for trend analysis and regression detection.
- **Response**: `200 OK`

---

## 3. Standard Error Envelope (RFC 7807)

```json
{
  "type": "https://reposcore.internal/errors/sandbox-timeout",
  "title": "Sandbox Execution Timeout",
  "status": 504,
  "detail": "Sandbox container exceeded allocated 300 second execution budget during step BUILDING.",
  "instance": "/evaluations/01925b4a-8cf2/steps/building",
  "correlation_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
  "timestamp": "2026-10-08T22:31:00Z"
}
```
