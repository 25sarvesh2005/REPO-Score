# JSONB Column Schemas & Payload Specifications

> **Document:** `JSONB_SCHEMAS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Persistence Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. Overview & Validation Rules

RepoScore uses PostgreSQL `JSONB` columns for semi-structured telemetry, findings, receipts, and configuration metadata. To avoid schema drift and data corruption:
- All JSONB payloads MUST validate against the rigid JSON Schema definitions specified herein.
- In Python application code, every JSONB column is mapped to a strongly typed **Pydantic v2** model before serialization.
- GIN indexes (`jsonb_path_ops`) are applied to enable high-speed querying on indexed sub-fields.

---

## 2. Repository & Snapshot Payloads

### 2.1 `repository_snapshots.detected_languages`
Map of detected programming languages to file statistics and proportion:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DetectedLanguagesSchema",
  "type": "object",
  "additionalProperties": {
    "type": "object",
    "required": ["percentage", "bytes", "file_count"],
    "properties": {
      "percentage": { "type": "number", "minimum": 0.0, "maximum": 100.0 },
      "bytes": { "type": "integer", "minimum": 0 },
      "file_count": { "type": "integer", "minimum": 1 }
    }
  }
}
```
*Example Instance:*
```json
{
  "Python": { "percentage": 85.4, "bytes": 450200, "file_count": 34 },
  "Shell": { "percentage": 14.6, "bytes": 77100, "file_count": 3 }
}
```

### 2.2 `repository_snapshots.detected_frameworks`
Array of framework descriptors identified during manifest inspection:
```json
[
  {
    "name": "FastAPI",
    "version_spec": ">=0.100.0",
    "ecosystem": "pypi",
    "confidence": 1.0,
    "manifest_file": "pyproject.toml"
  }
]
```

### 2.3 `repository_snapshots.detected_entrypoints`
Array of discovered executable entrypoints and startup commands:
```json
[
  {
    "type": "WEB_SERVER",
    "command": "uvicorn main:app --host 0.0.0.0 --port 8000",
    "module": "main.py",
    "port": 8000,
    "confidence": 0.95
  }
]
```

---

## 3. Evaluation Lifecycle & Step Payloads

### 3.1 `evaluation_steps.step_metadata`
Execution metrics, container identifiers, and diagnostics for an individual step:
```json
{
  "container_id": "c1a2b3c4d5e6",
  "sandbox_runtime": "docker-runc",
  "retry_count": 0,
  "memory_peak_bytes": 142606336,
  "cpu_time_user_ms": 1240,
  "cpu_time_system_ms": 310,
  "output_truncated": false,
  "exit_signal": null
}
```

---

## 4. Evidence & Finding Payloads

### 4.1 `evidence.location`
Physical source location within the snapshot repository:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EvidenceLocationSchema",
  "type": "object",
  "required": ["file_path"],
  "properties": {
    "file_path": { "type": "string", "maxLength": 512 },
    "start_line": { "type": "integer", "minimum": 1 },
    "end_line": { "type": "integer", "minimum": 1 },
    "start_col": { "type": "integer", "minimum": 1 },
    "end_col": { "type": "integer", "minimum": 1 },
    "ast_node_type": { "type": "string" },
    "symbol_name": { "type": "string" }
  }
}
```
*Example Instance:*
```json
{
  "file_path": "backend/auth/security.py",
  "start_line": 42,
  "end_line": 45,
  "start_col": 8,
  "end_col": 32,
  "ast_node_type": "call_expression",
  "symbol_name": "eval"
}
```

### 4.2 `evidence.normalized_attributes`
Dimension-specific normalized attributes used by the scoring engine:
```json
{
  "rule_id": "SEMGREP-PYTHON-INSECURE-EVAL",
  "analyzer_name": "semgrep",
  "cwe_id": "CWE-95",
  "owasp_category": "A03:2021-Injection",
  "cyclomatic_complexity": null,
  "cvss_v3_score": 8.8,
  "is_dependency": false
}
```

### 4.3 `evidence.raw_payload`
Sanitized raw snippet from the analyzer tool output:
```json
{
  "raw_tool": "semgrep",
  "rule_url": "https://semgrep.dev/r/python.lang.security.eval",
  "raw_lines": "result = eval(user_input)",
  "tool_exit_code": 0
}
```

---

## 5. Telemetry & Scoring Receipts

### 5.1 `runtime_observations.metadata`
Structured metric details for HTTP probes or process telemetry:
```json
{
  "probe_url": "http://127.0.0.1:8000/health",
  "http_status": 200,
  "latency_ms": 14.2,
  "response_bytes": 42,
  "content_type": "application/json",
  "error": null
}
```

### 5.2 `score_dimensions.itemized_receipt`
Array of itemized deduction and credit receipts backing each dimension score:
```json
[
  {
    "type": "DEDUCTION",
    "rule_code": "RULE_CRITICAL_SECURITY_VULNERABILITY",
    "evidence_id": "01925b4a-e011-7000-8000-000000000001",
    "description": "Hardcoded AWS secret key discovered in backend/config.py",
    "severity": "CRITICAL",
    "points": 25.0,
    "confidence": 1.0,
    "calculated_deduction": 25.0
  },
  {
    "type": "CREDIT",
    "rule_code": "CREDIT_CLEAN_BUILD",
    "evidence_id": "01925b4a-e022-7000-8000-000000000002",
    "description": "Clean dependency build with zero compiler warnings",
    "severity": "INFO",
    "points": 10.0,
    "confidence": 1.0,
    "calculated_credit": 10.0
  }
]
```

### 5.3 `recommendations.actionable_steps`
Ordered list of concrete steps for engineering remediation:
```json
[
  "Remove hardcoded AWS access key from backend/config.py.",
  "Configure environment variables or AWS IAM roles for secret delivery.",
  "Rotate the exposed AWS access key immediately in AWS IAM console."
]
```

### 5.4 `evaluation_events.payload`
Real-time SSE event body dispatched to frontend clients:
```json
{
  "step": "BUILDING",
  "progress_percent": 45,
  "status": "IN_PROGRESS",
  "message": "Installing Python dependencies via pip...",
  "elapsed_seconds": 28
}
```
