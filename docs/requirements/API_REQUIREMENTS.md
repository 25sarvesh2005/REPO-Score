# API Requirements Specification (API)

> **Document:** `API_REQUIREMENTS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Requirements Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. API Architecture Principles

The RepoScore API Layer acts as a stateless, high-throughput gateway built with **FastAPI** and **Pydantic v2**:
1. **Stateless Operations:** API pods handle request validation, rate limiting, and persistence queries, delegating compute-intensive jobs to Redis worker queues.
2. **Strict Schema Typing:** All request bodies and response envelopes adhere to strict Pydantic schemas documented in OpenAPI 3.1.
3. **Structured RFC 7807 Errors:** All non-2xx responses MUST return Problem Details JSON payloads.
4. **Traceability:** Every request requires or auto-generates a distributed `correlation_id` returned in `X-Correlation-ID`.

---

## 2. Core Endpoint Specifications

### API-001: Register / Ingest Repository (`POST /repositories`)
- **Priority:** P0
- **Method / Path:** `POST /repositories`
- **Description:** Validates repository reference, checks remote accessibility, creates a `repositories` record, and returns the entity.
- **Request Body:**
  ```json
  {
    "url": "https://github.com/fastapi/fastapi",
    "provider": "github"
  }
  ```
- **Response:** `201 Created`
  ```json
  {
    "id": "01925b4a-1000-7000-8000-000000000001",
    "url": "https://github.com/fastapi/fastapi",
    "owner": "fastapi",
    "name": "fastapi",
    "default_branch": "master",
    "created_at": "2026-10-12T13:00:00Z"
  }
  ```
- **Acceptance Criteria:**
  ```gherkin
  Given a valid GitHub repository URL
  When a client sends POST /repositories
  Then the API must respond with 201 Created within 200ms
  And return the persisted repository metadata
  ```

### API-002: Fetch Repository Details (`GET /repositories/{id}`)
- **Priority:** P1
- **Method / Path:** `GET /repositories/{id}`
- **Description:** Retrieves repository record, metadata stats (stars, forks, primary language), and associated snapshots.
- **Response:** `200 OK`

### API-003: Enqueue Evaluation (`POST /evaluations`)
- **Priority:** P0
- **Method / Path:** `POST /evaluations`
- **Description:** Enqueues an evaluation job for a repository against an optional ref or branch. Returns HTTP `202 Accepted` with correlation details and status URL.
- **Request Body:**
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
- **Response:** `202 Accepted`
  ```json
  {
    "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
    "status": "QUEUED",
    "correlation_id": "01925b4a-8d1a-7b3c-9a40-e2b8fa492001",
    "status_url": "/evaluations/01925b4a-8cf2-7612-882f-3d18c9ba1100/status"
  }
  ```
- **Acceptance Criteria:**
  ```gherkin
  Given an existing repository ID
  When POST /evaluations is submitted
  Then the API must return 202 Accepted
  And the response Location header must point to "/evaluations/{id}/status"
  ```

### API-004: Evaluation Summary Record (`GET /evaluations/{id}`)
- **Priority:** P0
- **Method / Path:** `GET /evaluations/{id}`
- **Description:** Returns the complete master record of an evaluation, including current status, duration, error messages, target commit SHA, and timestamps.
- **Response:** `200 OK`

### API-005: Lightweight Status Polling (`GET /evaluations/{id}/status`)
- **Priority:** P0
- **Method / Path:** `GET /evaluations/{id}/status`
- **Description:** High-frequency, lightweight polling endpoint returning active lifecycle state, current sub-step, and elapsed execution time.
- **Response:** `200 OK`
  ```json
  {
    "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
    "status": "BUILDING",
    "current_step": "compiling_application",
    "elapsed_seconds": 42
  }
  ```

### API-006: Real-time Event Streaming (`GET /evaluations/{id}/events`)
- **Priority:** P1
- **Method / Path:** `GET /evaluations/{id}/events`
- **Description:** Server-Sent Events (SSE) stream delivering real-time lifecycle transitions, step starts/completions, and progressive findings as they occur.
- **Headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`

### API-007: Evaluation Cancellation (`POST /evaluations/{id}/cancel`)
- **Priority:** P0
- **Method / Path:** `POST /evaluations/{id}/cancel`
- **Description:** Signals the worker pool to immediately terminate active sandbox processes and transition the evaluation to `CANCELLED`.
- **Response:** `200 OK`
  ```json
  {
    "evaluation_id": "01925b4a-8cf2-7612-882f-3d18c9ba1100",
    "status": "CANCELLED",
    "message": "Cancellation request dispatched to active workers."
  }
  ```

### API-008: Deterministic Scorecard (`GET /evaluations/{id}/score`)
- **Priority:** P0
- **Method / Path:** `GET /evaluations/{id}/score`
- **Description:** Retrieves finalized deterministic scores: overall composite score (0-100), letter grade (A+ to F), scoring version, and all 10 dimension receipts.
- **Response:** `200 OK`
- **Acceptance Criteria:**
  ```gherkin
  Given a completed evaluation
  When GET /evaluations/{id}/score is invoked
  Then the response must return composite_score, letter_grade, scoring_version
  And must return all 10 dimension scores with itemized receipts
  ```

### API-009: Paginated Evidence Exploration (`GET /evaluations/{id}/evidence`)
- **Priority:** P0
- **Method / Path:** `GET /evaluations/{id}/evidence`
- **Description:** Retrieves paginated, filterable list of normalized evidence items.
- **Query Parameters:**
  - `category`: optional filter (`SECURITY`, `CORRECTNESS`, `PERFORMANCE`, etc.)
  - `severity`: optional filter (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`)
  - `limit`: integer, default 50, max 200
  - `offset`: integer, default 0
- **Response:** `200 OK`

### API-010: Runtime Probing & Telemetry Results (`GET /evaluations/{id}/runtime`)
- **Priority:** P0
- **Method / Path:** `GET /evaluations/{id}/runtime`
- **Description:** Exposes runtime execution observations: startup time, synthetic probe responses, exit codes, CPU/RAM telemetry, and test execution summaries.
- **Response:** `200 OK`

### API-011: Security Findings Summary (`GET /evaluations/{id}/security`)
- **Priority:** P0
- **Method / Path:** `GET /evaluations/{id}/security`
- **Description:** Exposes dedicated security report: dependency CVEs (OSV), hardcoded secret discoveries, and dangerous code pattern violations.
- **Response:** `200 OK`

### API-012: Static Findings Explorer (`GET /evaluations/{id}/findings`)
- **Priority:** P1
- **Method / Path:** `GET /evaluations/{id}/findings`
- **Description:** Lists raw and normalized static analysis findings across all analyzers (Tree-sitter, Semgrep, Ruff, Bandit).
- **Response:** `200 OK`

### API-013: Cross-Evaluation Historical Trends (`GET /evaluations/{id}/history`)
- **Priority:** P1
- **Method / Path:** `GET /evaluations/{id}/history`
- **Description:** Returns historical evaluations for the same repository to evaluate score trends and newly introduced or fixed findings.
- **Response:** `200 OK`

### API-014: Service Liveness Probe (`GET /health`)
- **Priority:** P0
- **Method / Path:** `GET /health`
- **Description:** Liveness probe returning `200 OK` if the FastAPI gateway is responsive.
- **Response:** `200 OK` (`{"status": "healthy"}`)

### API-015: Service Readiness Probe (`GET /ready`)
- **Priority:** P0
- **Method / Path:** `GET /ready`
- **Description:** Readiness probe validating connectivity to PostgreSQL and Redis. If either service is unreachable, returns `503 Service Unavailable`.
- **Response:** `200 OK` or `503 Service Unavailable`
- **Acceptance Criteria:**
  ```gherkin
  Given the PostgreSQL database is unreachable
  When GET /ready is invoked
  Then the API must return HTTP 503 Service Unavailable
  And detail the failed dependency in the JSON response
  ```

---

## 3. General API Standards & Protocols

### API-016: Structured RFC 7807 Problem Details
- **Priority:** P0
- **Category:** Error Handling
- **Description:** All 4xx and 5xx responses MUST adhere to RFC 7807 JSON schema containing: `type`, `title`, `status`, `detail`, `instance`, `correlation_id`, and `timestamp`.

### API-017: Distributed Correlation Header (`X-Correlation-ID`)
- **Priority:** P0
- **Category:** Observability
- **Description:** The API MUST accept client-provided `X-Correlation-ID` or generate a new UUIDv7 if missing, returning the identifier in the response headers of every HTTP call.

### API-018: Idempotency Key Header (`Idempotency-Key`)
- **Priority:** P1
- **Category:** Reliability
- **Description:** `POST /evaluations` SHALL support an optional `Idempotency-Key` header. Repeated submissions with the same key within a 15-minute window SHALL return the original created evaluation record without creating duplicate Redis tasks.

### API-019: Rate Limiting & Abuse Prevention
- **Priority:** P1
- **Category:** Security
- **Description:** The API gateway SHALL enforce rate limits:
  - Evaluation creation (`POST /evaluations`): max 10 requests per minute per client IP.
  - Read endpoints: max 300 requests per minute per client IP.
  Excessive requests MUST return HTTP `429 Too Many Requests`.

### API-020: API Versioning Strategy
- **Priority:** P0
- **Category:** Contract Evolution
- **Description:** All endpoints SHALL be prefix-versioned under `/api/v1/` while maintaining backwards-compatible root aliases where needed. Breaking changes require `/api/v2/`.

### API-021: Pagination Standards
- **Priority:** P1
- **Category:** Usability
- **Description:** All collection endpoints (`/evidence`, `/findings`, `/history`) SHALL use standard `limit` (max 200) and `offset` query parameters, returning pagination metadata in the response: `total_count`, `limit`, `offset`, `has_more`.

### API-022: Future Authentication Boundary
- **Priority:** P2
- **Category:** Extensibility
- **Description:** The API architecture SHALL define dependency injection hooks (`get_current_user`) to support future API token authentication (Bearer JWT or API Keys) without changing route logic.
