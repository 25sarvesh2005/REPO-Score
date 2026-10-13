"""
Evaluation Pipeline Orchestration Domain Models.
Adheres strictly to EVALUATION_LIFECYCLE.md and Prime Directives.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from backend.api.schemas.contracts import EvaluationStatus, LetterGrade


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


@dataclass
class StepExecutionLog:
    step_name: str
    status: StepStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    step_id: uuid.UUID | None = None
    evaluation_id: uuid.UUID | None = None


@dataclass
class PipelineExecutionResult:
    evaluation_id: uuid.UUID
    repository_id: uuid.UUID
    status: EvaluationStatus
    overall_score: Decimal | None = None
    grade: LetterGrade | None = None
    evidence_count: int = 0
    duration_ms: int = 0
    steps_executed: list[StepExecutionLog] = field(default_factory=list)
    error_summary: str | None = None
    is_partial: bool = False
    is_cancelled: bool = False
