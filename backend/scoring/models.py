"""
Domain models and schema definitions for deterministic scorecard calculations and receipts.
Adheres strictly to SCORING_ARCHITECTURE.md, ADR-004, and SCORE-021 through SCORE-023.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.contracts import (
    EvidenceCategory,
    ItemizedReceiptItem,
    LetterGrade,
    ScorecardResponse,
    ScoreDimensionResponse,
)


class ReceiptItem(BaseModel):
    """
    Itemized transparent receipt entry attributing a deduction or credit to specific evidence.
    Adheres strictly to SCORE-010 (Evidence Attribution Invariant) and SCORE-021.
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="DEDUCTION or CREDIT")
    rule_code: str = Field(
        ..., description="Standardized rule code (e.g. RULE_SEC_HARDCODED_SECRET)"
    )
    evidence_id: UUID = Field(..., description="Foreign key to the underlying Evidence record")
    description: str = Field(..., description="Human-readable explanation of deduction or credit")
    points: Decimal = Field(..., ge=0, description="Absolute base point magnitude")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Analyzer confidence score (0.0 - 1.0)"
    )
    calculated_delta: Decimal = Field(
        ..., description="Net signed point adjustment applied to dimension score"
    )

    def to_contract_item(self) -> ItemizedReceiptItem:
        """Convert to API schema ItemizedReceiptItem."""
        return ItemizedReceiptItem(
            type=self.type,
            rule_code=self.rule_code,
            evidence_id=self.evidence_id,
            description=self.description,
            points=self.points,
            confidence=self.confidence,
            calculated_delta=self.calculated_delta,
        )


class DimensionScoreResult(BaseModel):
    """
    Deterministic score evaluation outcome for a single engineering dimension.
    """

    model_config = ConfigDict(extra="forbid")

    dimension_name: str = Field(..., description="Capitalized human-readable dimension name")
    category: EvidenceCategory = Field(..., description="Standardized dimension category enum")
    weight: Decimal = Field(
        ..., ge=0, le=1, description="Dimension weight multiplier (summing to 1.00)"
    )
    base_score: Decimal = Field(default=Decimal("100.0"), description="Starting baseline score")
    score: Decimal = Field(..., ge=0, le=100, description="Clamped dimension score [0.0, 100.0]")
    status: str = Field(
        default="COMPLETED", description="COMPLETED or EVALUATION_INCOMPLETE (SCORE-023)"
    )
    receipt: list[ReceiptItem] = Field(
        default_factory=list, description="Itemized list of deductions and credits"
    )
    total_deductions: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Sum of all deduction points"
    )
    total_credits: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Sum of all credit points"
    )

    def to_dimension_response(self) -> ScoreDimensionResponse:
        """Convert to API schema ScoreDimensionResponse."""
        return ScoreDimensionResponse(
            dimension_name=self.dimension_name,
            score=self.score,
            weight=self.weight,
            base_score=self.base_score,
            itemized_receipt=[item.to_contract_item() for item in self.receipt],
        )


class ScorecardResult(BaseModel):
    """
    Complete immutable evaluation scorecard and mathematical receipt.
    """

    model_config = ConfigDict(extra="forbid")

    evaluation_id: UUID = Field(..., description="Parent evaluation UUID")
    scoring_version: str = Field(
        default="1.0.0", description="Semver string of scoring ruleset (SCORE-008)"
    )
    overall_score: Decimal = Field(
        ..., ge=0, le=100, description="Weighted composite score rounded to 1 decimal"
    )
    grade: LetterGrade = Field(..., description="Standard letter grade (A+, A, B, C, D, F)")
    dimensions: dict[str, DimensionScoreResult] = Field(
        ..., description="Dimension scorecard breakdown keyed by EvidenceCategory name"
    )
    total_deductions: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Aggregated deduction points"
    )
    total_credits: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Aggregated credit points"
    )
    evidence_count: int = Field(default=0, ge=0, description="Total evidence items evaluated")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Evaluation timestamp"
    )

    def to_scorecard_response(self, ai_summary: str | None = None) -> ScorecardResponse:
        """Convert to API schema ScorecardResponse."""
        sorted_dims = [dim.to_dimension_response() for dim in self.dimensions.values()]
        return ScorecardResponse(
            evaluation_id=self.evaluation_id,
            scoring_version=self.scoring_version,
            overall_score=self.overall_score,
            grade=self.grade,
            dimensions=sorted_dims,
            ai_executive_summary=ai_summary,
            created_at=self.evaluated_at,
        )
