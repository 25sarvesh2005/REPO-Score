# Pydantic v2 Request & Response Schema Models

> **Document:** `PYDANTIC_SCHEMAS.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / API Contract Baseline  
> **Authority:** [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/SYSTEM_ARCHITECTURE.md), [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md)

---

## 1. Overview & Validation Rules

This document specifies the exact **Pydantic v2** models implemented in `backend/api/schemas/` for request body parsing, query parameter validation, and response serialization:
- Models inherit from `pydantic.BaseModel` configured with `model_config = ConfigDict(from_attributes=True, extra="forbid")`.
- Identifiers use standard `uuid.UUID` (conforming to RFC 9562 / UUIDv7).
- Timestamps use timezone-aware `datetime.datetime`.
- Scores use `decimal.Decimal` to ensure exact decimal representation without binary floating-point roundoff errors.

---

## 2. Python Code Specification

```python
"""
RepoScore Pydantic v2 API Contracts
Target path: backend/api/schemas/contracts.py
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ============================================================================
# 1. Enums
# ============================================================================

class EvaluationStatus(str, Enum):
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    ANALYZING = "ANALYZING"
    BUILDING = "BUILDING"
    STARTING = "STARTING"
    TESTING = "TESTING"
    OBSERVING = "OBSERVING"
    SCORING = "SCORING"
    AI_INTERPRETATION = "AI_INTERPRETATION"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    BUILD_FAILED = "BUILD_FAILED"
    STARTUP_FAILED = "STARTUP_FAILED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    UNSUPPORTED = "UNSUPPORTED"

class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class EvidenceCategory(str, Enum):
    CORRECTNESS = "CORRECTNESS"
    SECURITY = "SECURITY"
    RELIABILITY = "RELIABILITY"
    TESTING = "TESTING"
    MAINTAINABILITY = "MAINTAINABILITY"
    ARCHITECTURE = "ARCHITECTURE"
    PERFORMANCE = "PERFORMANCE"
    DEPENDENCY_HEALTH = "DEPENDENCY_HEALTH"
    DOCUMENTATION = "DOCUMENTATION"
    ENGINEERING_MATURITY = "ENGINEERING_MATURITY"

class LetterGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"

# ============================================================================
# 2. RFC 7807 Problem Details
# ============================================================================

class InvalidParam(BaseModel):
    name: str
    reason: str

class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(..., description="URI reference identifying problem type")
    title: str = Field(..., description="Short summary of problem")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation")
    instance: str = Field(..., description="URI reference of specific occurrence")
    correlation_id: UUID = Field(..., description="Distributed tracing identifier")
    timestamp: datetime = Field(..., description="UTC timestamp of occurrence")
    invalid_params: List[InvalidParam] = Field(default_factory=list)

# ============================================================================
# 3. Repository Schemas
# ============================================================================

class RepositoryRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl = Field(..., description="Public GitHub repository URL")
    provider: str = Field(default="github", max_length=32)

class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    owner: str
    name: str
    default_branch: str
    is_private: bool
    stars_count: int
    primary_language: Optional[str] = None
    created_at: datetime

# ============================================================================
# 4. Evaluation Schemas
# ============================================================================

class EvaluationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_seconds: int = Field(default=600, ge=60, le=1800)
    enable_ai_reasoning: bool = Field(default=True)

class EvaluationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: UUID
    ref: Optional[str] = Field(default="main", max_length=128)
    options: EvaluationOptions = Field(default_factory=EvaluationOptions)

class EvaluationAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    status: EvaluationStatus
    correlation_id: UUID
    status_url: str
    events_url: str

class EvaluationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    repository_id: UUID
    snapshot_id: UUID
    status: EvaluationStatus
    correlation_id: UUID
    trigger_source: str
    worker_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_summary: Optional[str] = None
    created_at: datetime

class EvaluationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    status: EvaluationStatus
    current_step: Optional[str] = None
    elapsed_seconds: int
    is_terminal: bool

class EvaluationCancelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    status: str = "CANCELLED"
    message: str

# ============================================================================
# 5. Scorecard & Results Schemas
# ============================================================================

class ItemizedReceiptItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(..., description="DEDUCTION or CREDIT")
    rule_code: str
    evidence_id: UUID
    description: str
    points: Decimal = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    calculated_delta: Decimal

class ScoreDimensionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dimension_name: str
    score: Decimal = Field(..., ge=0, le=100)
    weight: Decimal = Field(..., ge=0, le=1)
    base_score: Decimal = Decimal("100.0")
    itemized_receipt: List[ItemizedReceiptItem] = Field(default_factory=list)

class ScorecardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evaluation_id: UUID
    scoring_version: str = "1.0.0"
    overall_score: Decimal = Field(..., ge=0, le=100)
    grade: LetterGrade
    dimensions: List[ScoreDimensionResponse]
    ai_executive_summary: Optional[str] = None
    created_at: datetime

# ============================================================================
# 6. Evidence Schemas
# ============================================================================

class EvidenceLocation(BaseModel):
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_col: Optional[int] = None
    end_col: Optional[int] = None
    symbol_name: Optional[str] = None

class EvidenceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    category: EvidenceCategory
    severity: SeverityLevel
    confidence: float
    title: str
    description: str
    location: Optional[EvidenceLocation] = None
    created_at: datetime

class PaginatedEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: List[EvidenceItemResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool

# ============================================================================
# 7. Operational Health Schemas
# ============================================================================

class HealthResponse(BaseModel):
    status: str = "healthy"

class ReadinessResponse(BaseModel):
    status: str = "ready"
    database: str = "connected"
    redis: str = "connected"
```
