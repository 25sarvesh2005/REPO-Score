# API Contract Test Plan & Verification Matrix

> **Document:** `API_CONTRACT_TEST_PLAN.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / API Contract Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. Objective & Scope

This document specifies the contract testing methodology, verification suites, and automated assertions to ensure that the FastAPI implementation in Phase 05 strictly satisfies the OpenAPI 3.1.0 specifications and Pydantic schemas defined in [OPENAPI_SPEC.yaml](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/api/OPENAPI_SPEC.yaml) and [PYDANTIC_SCHEMAS.md](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/api/PYDANTIC_SCHEMAS.md).

---

## 2. Master API Contract Test Matrix

| Test ID | Endpoint & Method | Contract Invariant | Verification Method | Expected Result |
|---|---|---|---|---|
| **API-TEST-01** | `POST /api/v1/repositories` | Input schema validation | Submit valid GitHub URL | HTTP `201 Created` + valid `RepositoryResponse` |
| **API-TEST-02** | `POST /api/v1/repositories` | Rejection of invalid URL | Submit `"not-a-url"` | HTTP `400 Bad Request` + RFC 7807 problem details |
| **API-TEST-03** | `GET /api/v1/repositories/{id}` | Path parameter parsing | Query with valid UUID | HTTP `200 OK` + matching repository ID |
| **API-TEST-04** | `GET /api/v1/repositories/{id}` | Not found handling | Query non-existent UUID | HTTP `404 Not Found` + RFC 7807 problem details |
| **API-TEST-05** | `POST /api/v1/evaluations` | Asynchronous 202 handoff | Valid submission | HTTP `202 Accepted` + Location header |
| **API-TEST-06** | `POST /api/v1/evaluations` | Idempotency key handling | Submit duplicate request with same `Idempotency-Key` | HTTP `202 Accepted` (replays original, 0 duplicate jobs) |
| **API-TEST-07** | `GET /api/v1/evaluations/{id}/status` | Fast status polling | Poll active evaluation | HTTP `200 OK` + `EvaluationStatusResponse` |
| **API-TEST-08** | `GET /api/v1/evaluations/{id}/events` | SSE protocol conformance | Connect to event stream | `Content-Type: text/event-stream` + valid frames |
| **API-TEST-09** | `GET /api/v1/evaluations/{id}/events` | Replay via `Last-Event-ID` | Connect with header | Replays missed events from PostgreSQL |
| **API-TEST-10** | `POST /api/v1/evaluations/{id}/cancel` | Cancellation signaling | Submit cancel on active job | HTTP `200 OK` + status `CANCELLED` |
| **API-TEST-11** | `GET /api/v1/evaluations/{id}/score` | Finalized scorecard schema | Query completed eval | HTTP `200 OK` + `ScorecardResponse` with 10 dims |
| **API-TEST-12** | `GET /api/v1/evaluations/{id}/score` | In-progress conflict | Query evaluation in `BUILDING` | HTTP `409 Conflict` + problem details |
| **API-TEST-13** | `GET /api/v1/evaluations/{id}/evidence` | Pagination & filtering | Query with `limit=10&offset=0` | HTTP `200 OK` + `PaginatedEvidenceResponse` |
| **API-TEST-14** | `GET /api/v1/evaluations/{id}/runtime` | Runtime telemetry contract | Query completed eval | HTTP `200 OK` + observations list |
| **API-TEST-15** | `GET /api/v1/evaluations/{id}/security` | Security findings contract | Query completed eval | HTTP `200 OK` + CVE & secret findings |
| **API-TEST-16** | `GET /health` | Liveness probe contract | HTTP GET | HTTP `200 OK` (`{"status":"healthy"}`) |
| **API-TEST-17** | `GET /ready` | Readiness probe contract | HTTP GET with DB/Redis up | HTTP `200 OK` (`{"status":"ready",...}`) |
| **API-TEST-18** | `GET /ready` | Readiness failure contract | HTTP GET with DB mocked down | HTTP `503 Service Unavailable` + problem details |
| **API-TEST-19** | All Endpoints | Correlation ID propagation | Supply `X-Correlation-ID: {uuid}` | Response header matches input correlation ID |
| **API-TEST-20** | All Endpoints | Correlation ID generation | Omit `X-Correlation-ID` header | Response header contains newly generated UUIDv7 |
| **API-TEST-21** | All Endpoints | Rate limiting enforcement | Send 15 POSTs in 5 seconds | HTTP `429 Too Many Requests` + rate limit headers |
| **API-TEST-22** | All Endpoints | RFC 7807 schema validation | Trigger arbitrary 4xx/5xx | Response strictly validates against ProblemDetails |

---

## 3. Schemathesis Automated OpenAPI Fuzzing

In addition to discrete unit tests, Phase 05 CI pipelines will execute **Schemathesis** against the running FastAPI test server:
```bash
schemathesis run docs/api/OPENAPI_SPEC.yaml \
  --base-url=http://127.0.0.1:8000/api/v1 \
  --checks=all \
  --validate-schema=true \
  --hypothesis-max-examples=100
```
- **Conformity Checks:**
  1. `not_a_server_error`: No unexpected 500 exceptions on edge-case inputs.
  2. `status_code_conformance`: Every response status code is explicitly declared in the OpenAPI spec.
  3. `content_type_conformance`: Response headers match declared MIME types.
  4. `response_schema_conformance`: Response bodies strictly match JSON schemas.
