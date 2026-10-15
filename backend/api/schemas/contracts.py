"""
RepoScore Pydantic v2 API Contracts.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
    primary_language: str | None = None
    created_at: datetime


class EvaluationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_seconds: int = Field(default=600, ge=60, le=1800)
    enable_ai_reasoning: bool = Field(default=True)


class EvaluationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: UUID
    ref: str | None = Field(default="main", max_length=128)
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
    worker_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error_summary: str | None = None
    overall_score: Decimal | None = None
    grade: LetterGrade | None = None
    created_at: datetime


class EvaluationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    status: EvaluationStatus
    current_step: str | None = None
    elapsed_seconds: int
    is_terminal: bool


class EvaluationCancelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    status: str = "CANCELLED"
    message: str


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
    itemized_receipt: list[ItemizedReceiptItem] = Field(default_factory=list)


class ScorecardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evaluation_id: UUID
    scoring_version: str = "1.0.0"
    overall_score: Decimal = Field(..., ge=0, le=100)
    grade: LetterGrade
    dimensions: list[ScoreDimensionResponse]
    ai_executive_summary: str | None = None
    created_at: datetime


class EvidenceLocation(BaseModel):
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    start_col: int | None = None
    end_col: int | None = None
    symbol_name: str | None = None


class EvidenceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    category: EvidenceCategory
    severity: SeverityLevel
    confidence: float
    title: str
    description: str
    location: EvidenceLocation | None = None
    created_at: datetime


class PaginatedEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[EvidenceItemResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class HealthResponse(BaseModel):
    status: str = "healthy"


class ReadinessResponse(BaseModel):
    status: str = "ready"
    database: str = "connected"
    redis: str = "connected"


class RuntimeTelemetryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    evaluator_strategy: str = "generic"
    build_success: bool | None = None
    build_exit_code: int | None = None
    startup_ready: bool | None = None
    startup_port: int | None = None
    latency_p95_ms: float | None = None
    total_http_requests: int = 0
    error_5xx_requests: int = 0
    failure_code: str | None = None
    failure_reason: str | None = None
    observations: list[dict] = Field(default_factory=list)


class AIInterpretationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    provider: str
    model_name: str
    prompt_version: str = "1.0.0"
    executive_summary: str
    architectural_assessment: str
    security_risk_narrative: str
    runtime_failure_root_cause: str | None = None
    top_strengths: list[str] = Field(default_factory=list)
    critical_risks: list[str] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    tokens_consumed: int | None = None
    duration_ms: int | None = None
    is_fallback: bool = False


class EvaluationHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    repository_id: UUID
    status: EvaluationStatus
    commit_sha: str | None = None
    overall_score: Decimal | None = None
    grade: LetterGrade | None = None
    created_at: datetime
    duration_ms: int | None = None
