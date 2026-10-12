"""
Evaluation Pipeline Orchestration Domain Models.
Adheres strictly to EVALUATION_LIFECYCLE.md and Prime Directives.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

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
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineExecutionResult:
    evaluation_id: uuid.UUID
    repository_id: uuid.UUID
    status: EvaluationStatus
    overall_score: Optional[Decimal] = None
    grade: Optional[LetterGrade] = None
    evidence_count: int = 0
    duration_ms: int = 0
    steps_executed: List[StepExecutionLog] = field(default_factory=list)
    error_summary: Optional[str] = None
    is_partial: bool = False
    is_cancelled: bool = False
