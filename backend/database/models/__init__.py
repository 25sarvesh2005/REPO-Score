"""
SQLAlchemy 2.0 ORM Models matching Phase 03 Schema Specification.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    CHAR,
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.api.schemas.contracts import (
    EvaluationStatus,
    EvidenceCategory,
    SeverityLevel,
)
from backend.database.base import TimestampedBase


# SQLite compatibility rules for local/development and portable environments
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


class PortableArray(TypeDecorator):
    """
    Transparently falls back to JSON serialization for SQLite / non-PostgreSQL dialects.
    Uses native postgresql.ARRAY on PostgreSQL.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, item_type=String, *args, **kwargs):
        self.item_type = item_type
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

            return dialect.type_descriptor(PG_ARRAY(self.item_type))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return None
        return [str(v) if isinstance(v, uuid.UUID) else v for v in value]

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return []
        if isinstance(value, str):
            import json

            try:
                return json.loads(value)
            except Exception:
                return []
        return value


ARRAY = PortableArray


class Repository(TimestampedBase):
    __tablename__ = "repositories"

    url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(64), default="main", nullable=False)
    is_private: Mapped[bool] = mapped_column(BOOLEAN, default=False, nullable=False)
    stars_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    forks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    license_spdx: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    snapshots: Mapped[list["RepositorySnapshot"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class RepositorySnapshot(TimestampedBase):
    __tablename__ = "repository_snapshots"
    __table_args__ = (UniqueConstraint("repository_id", "commit_sha", name="uq_repo_commit"),)

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(CHAR(40), nullable=False)
    tree_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    branch_or_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_languages: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    detected_frameworks: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    detected_entrypoints: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)

    repository: Mapped["Repository"] = relationship(back_populates="snapshots")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class Evaluation(TimestampedBase):
    __tablename__ = "evaluations"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status_enum"),
        default=EvaluationStatus.QUEUED,
        nullable=False,
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="evaluations")
    snapshot: Mapped["RepositorySnapshot"] = relationship(back_populates="evaluations")
    steps: Mapped[list["EvaluationStep"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )
    score: Mapped[Optional["Score"]] = relationship(
        back_populates="evaluation", uselist=False, cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )
    ai_analysis: Mapped[Optional["AIAnalysis"]] = relationship(
        back_populates="evaluation", uselist=False, cascade="all, delete-orphan"
    )


class EvaluationStep(TimestampedBase):
    __tablename__ = "evaluation_steps"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="steps")


class ExecutionEnvironment(TimestampedBase):
    __tablename__ = "execution_environments"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    container_id: Mapped[str] = mapped_column(String(128), nullable=False)
    base_image: Mapped[str] = mapped_column(String(256), nullable=False)
    runtime_type: Mapped[str] = mapped_column(String(32), default="DOCKER_RUNC", nullable=False)
    cpu_quota: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), default=Decimal("2.0"), nullable=False
    )
    memory_limit_bytes: Mapped[int] = mapped_column(BIGINT, default=2147483648, nullable=False)
    pids_limit: Mapped[int] = mapped_column(Integer, default=128, nullable=False)
    network_policy: Mapped[str] = mapped_column(String(32), default="NONE", nullable=False)
    capabilities_dropped: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    uid_enforced: Mapped[int] = mapped_column(Integer, default=10001, nullable=False)
    gid_enforced: Mapped[int] = mapped_column(Integer, default=10001, nullable=False)
    seccomp_profile_digest: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)


class TestScenario(TimestampedBase):
    __tablename__ = "test_scenarios"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(32), nullable=False)
    command_executed: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stdout_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class RuntimeObservation(TimestampedBase):
    __tablename__ = "runtime_observations"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    metric_value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    metric_value_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )


class StaticFinding(TimestampedBase):
    __tablename__ = "static_findings"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_severity: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)


class SecurityFinding(TimestampedBase):
    __tablename__ = "security_findings"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    vulnerability_id: Mapped[str] = mapped_column(String(128), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    installed_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fixed_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cvss_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level_enum"), nullable=False
    )
    cwe_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Evidence(TimestampedBase):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("evaluation_id", "fingerprint", name="uq_eval_fingerprint"),)

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[EvidenceCategory] = mapped_column(
        Enum(EvidenceCategory, name="evidence_category_enum"), nullable=False
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level_enum"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    normalized_attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    related_evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, nullable=False
    )

    evaluation: Mapped["Evaluation"] = relationship(back_populates="evidence")


class Score(TimestampedBase):
    __tablename__ = "scores"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    scoring_version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    grade: Mapped[str] = mapped_column(String(4), nullable=False)
    total_deductions: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0.0"), nullable=False
    )
    total_credits: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0.0"), nullable=False
    )

    evaluation: Mapped["Evaluation"] = relationship(back_populates="score")
    dimensions: Mapped[list["ScoreDimension"]] = relationship(
        back_populates="score_rel", cascade="all, delete-orphan"
    )


class ScoreDimension(TimestampedBase):
    __tablename__ = "score_dimensions"
    __table_args__ = (UniqueConstraint("score_id", "dimension_name", name="uq_score_dimension"),)

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scores.id", ondelete="CASCADE"), nullable=False
    )
    dimension_name: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    base_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100.0"), nullable=False
    )
    itemized_receipt: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)

    score_rel: Mapped["Score"] = relationship("Score", back_populates="dimensions")


class AIAnalysis(TimestampedBase):
    __tablename__ = "ai_analyses"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), default="ollama", nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    architectural_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_failure_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    security_risk_narrative: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_consumed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="ai_analysis")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="ai_analysis", cascade="all, delete-orphan"
    )


class Recommendation(TimestampedBase):
    __tablename__ = "recommendations"

    ai_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_analyses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    actionable_steps: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    related_evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, nullable=False
    )

    ai_analysis: Mapped["AIAnalysis"] = relationship(back_populates="recommendations")


class EvaluationEvent(TimestampedBase):
    __tablename__ = "evaluation_events"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
