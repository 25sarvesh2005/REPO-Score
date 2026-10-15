"""
Deterministic Scoring Calculator and Scorecard Assembly Engine.
Adheres strictly to SCORING_ARCHITECTURE.md, ADR-003, ADR-004, and SCORE-001 through SCORE-024.
Consumes normalized evidence ONLY; zero AI involvement.
"""

from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.contracts import EvidenceCategory
from backend.database.models import Score, ScoreDimension
from backend.scoring.models import (
    DimensionScoreResult,
    ReceiptItem,
    ScorecardResult,
)
from backend.scoring.rules import (
    RULE_MAX_CUMULATIVE_DEDUCTIONS,
    EvidenceAdapter,
    evaluate_evidence_item,
    round_points,
)
from backend.scoring.weights import (
    DIMENSION_SPECIFICATIONS,
    calculate_letter_grade,
)

SCORING_VERSION = "1.0.0"


class DeterministicScoringEngine:
    """
    Mathematical, 100% deterministic scoring calculator.
    Produces identical bit-for-bit results across repeated runs given identical evidence.
    """

    def __init__(self, version: str = SCORING_VERSION) -> None:
        self.version = version

    def compute_scorecard(
        self,
        evaluation_id: UUID,
        evidence_records: list[Any],
        repo_metadata: dict[str, Any] | None = None,
        partial_status: str | None = None,
    ) -> ScorecardResult:
        """
        Execute deterministic scoring algorithm over evidence records.
        """
        metadata = repo_metadata or {}
        dim_results: dict[str, DimensionScoreResult] = {}

        # 1. Initialize all 10 dimensions with baseline 100.0 (SCORE-001, SCORE-002)
        dim_deductions: dict[EvidenceCategory, list[ReceiptItem]] = {
            cat: [] for cat in EvidenceCategory
        }
        dim_credits: dict[EvidenceCategory, list[ReceiptItem]] = {
            cat: [] for cat in EvidenceCategory
        }

        # 2. Process all Evidence Records into Deductions
        for raw_evidence in evidence_records:
            adapter = EvidenceAdapter(raw_evidence)
            receipt_item = evaluate_evidence_item(adapter)
            if receipt_item:
                dim_deductions[adapter.category].append(receipt_item)

        # 3. Process Positive Credits (with deterministic evidence attribution, SCORE-010)
        # Helper to synthesize deterministic attribution UUID for platform credits
        def _credit_evidence_id(slug: str) -> UUID:
            return uuid5(NAMESPACE_DNS, f"reposcore.credit.{evaluation_id}.{slug}")

        # Correctness: Clean build and boot credit (SCORE-011)
        if metadata.get("build_successful") and metadata.get("startup_successful"):
            if not dim_deductions[EvidenceCategory.CORRECTNESS]:
                dim_credits[EvidenceCategory.CORRECTNESS].append(
                    ReceiptItem(
                        type="CREDIT",
                        rule_code="RULE_CORR_CLEAN_RUN",
                        evidence_id=_credit_evidence_id("clean-run"),
                        description="Application compiled and bootstrapped cleanly with zero errors",
                        points=Decimal("10.0"),
                        confidence=1.0,
                        calculated_delta=Decimal("10.0"),
                    )
                )

        # Testing: Clean test suite pass (SCORE-014)
        if metadata.get("tests_passed", 0) > 0 and metadata.get("tests_failed", 0) == 0:
            dim_credits[EvidenceCategory.TESTING].append(
                ReceiptItem(
                    type="CREDIT",
                    rule_code="RULE_TEST_ALL_PASSED",
                    evidence_id=_credit_evidence_id("all-tests-passed"),
                    description=f"All {metadata['tests_passed']} test cases passed with zero failures",
                    points=Decimal("10.0"),
                    confidence=1.0,
                    calculated_delta=Decimal("10.0"),
                )
            )

        # Testing: High coverage (SCORE-014)
        if metadata.get("line_coverage_percent", 0.0) >= 80.0:
            dim_credits[EvidenceCategory.TESTING].append(
                ReceiptItem(
                    type="CREDIT",
                    rule_code="RULE_TEST_HIGH_COVERAGE",
                    evidence_id=_credit_evidence_id("high-coverage"),
                    description=f"High test line coverage achieved ({metadata['line_coverage_percent']:.1f}% >= 80%)",
                    points=Decimal("15.0"),
                    confidence=1.0,
                    calculated_delta=Decimal("15.0"),
                )
            )

        # Reliability: Clean SIGTERM shutdown (SCORE-013)
        if metadata.get("clean_shutdown"):
            dim_credits[EvidenceCategory.RELIABILITY].append(
                ReceiptItem(
                    type="CREDIT",
                    rule_code="RULE_REL_CLEAN_SHUTDOWN",
                    evidence_id=_credit_evidence_id("clean-shutdown"),
                    description="Application process terminated cleanly upon receiving SIGTERM within 5s",
                    points=Decimal("10.0"),
                    confidence=1.0,
                    calculated_delta=Decimal("10.0"),
                )
            )

        # Dependency Health: Lockfile present (SCORE-018)
        if metadata.get("lockfile_present"):
            dim_credits[EvidenceCategory.DEPENDENCY_HEALTH].append(
                ReceiptItem(
                    type="CREDIT",
                    rule_code="RULE_DEP_LOCKFILE_PRESENT",
                    evidence_id=_credit_evidence_id("lockfile-present"),
                    description="Tamper-evident dependency lockfile present in repository",
                    points=Decimal("10.0"),
                    confidence=1.0,
                    calculated_delta=Decimal("10.0"),
                )
            )

        # Documentation: Comprehensive documentation present (SCORE-019)
        if metadata.get("has_readme"):
            dim_credits[EvidenceCategory.DOCUMENTATION].append(
                ReceiptItem(
                    type="CREDIT",
                    rule_code="RULE_DOC_COMPREHENSIVE",
                    evidence_id=_credit_evidence_id("readme-present"),
                    description="Repository contains comprehensive documentation and README",
                    points=Decimal("15.0"),
                    confidence=1.0,
                    calculated_delta=Decimal("15.0"),
                )
            )

        # Engineering Maturity: Active CI workflows (SCORE-020)
        if metadata.get("ci_cd_detected"):
            dim_credits[EvidenceCategory.ENGINEERING_MATURITY].append(
                ReceiptItem(
                    type="CREDIT",
                    rule_code="RULE_ENG_CI_PRESENT",
                    evidence_id=_credit_evidence_id("ci-workflow"),
                    description=f"Active CI workflow configured: {', '.join(metadata['ci_cd_detected'])}",
                    points=Decimal("20.0"),
                    confidence=1.0,
                    calculated_delta=Decimal("20.0"),
                )
            )

        # 4. Compute Dimension Scores with Clamping (SCORE-002)
        total_all_deductions = Decimal("0.0")
        total_all_credits = Decimal("0.0")
        composite_accum = Decimal("0.0")

        for category, spec in DIMENSION_SPECIFICATIONS.items():
            deductions = dim_deductions[category]
            category_credits = dim_credits[category]

            # Enforce bounded cumulative deduction caps per rule code (ADR-004)
            effective_deductions: list[ReceiptItem] = []
            rules_grouped: dict[str, list[ReceiptItem]] = {}
            for item in deductions:
                rules_grouped.setdefault(item.rule_code, []).append(item)

            dim_ded_sum = Decimal("0.0")
            for rule_code, items in rules_grouped.items():
                rule_raw_sum = sum((abs(i.calculated_delta) for i in items), Decimal("0.0"))
                rule_cap = RULE_MAX_CUMULATIVE_DEDUCTIONS.get(rule_code)

                if (
                    rule_cap is not None
                    and rule_raw_sum > rule_cap
                    and rule_raw_sum > Decimal("0.0")
                ):
                    scaling_factor = rule_cap / rule_raw_sum
                    rule_accum = Decimal("0.0")
                    for i, item in enumerate(items):
                        if i == len(items) - 1:
                            item_scaled = -(rule_cap - rule_accum)
                        else:
                            item_scaled = round_points(
                                -(abs(item.calculated_delta) * scaling_factor)
                            )
                            rule_accum += abs(item_scaled)

                        updated_item = item.model_copy(update={"calculated_delta": item_scaled})
                        effective_deductions.append(updated_item)
                        dim_ded_sum += abs(item_scaled)
                else:
                    for item in items:
                        effective_deductions.append(item)
                        dim_ded_sum += abs(item.calculated_delta)

            dim_cred_sum = sum((item.calculated_delta for item in category_credits), Decimal("0.0"))

            total_all_deductions += dim_ded_sum
            total_all_credits += dim_cred_sum

            # S_d = Clamp[0.0, 100.0](100.0 - Deductions + Credits)
            raw_score = Decimal("100.0") - dim_ded_sum + dim_cred_sum
            clamped_score = max(Decimal("0.0"), min(Decimal("100.0"), raw_score))
            final_dim_score = round_points(clamped_score)

            status = "COMPLETED"
            # Partial evaluation adjustment (SCORE-023)
            if partial_status in {"BUILD_FAILED", "STARTUP_FAILED"}:
                if category in {EvidenceCategory.PERFORMANCE, EvidenceCategory.RELIABILITY}:
                    status = "EVALUATION_INCOMPLETE"
                    # Apply standardized 25pt penalty for incomplete runtime
                    incomplete_ded = ReceiptItem(
                        type="DEDUCTION",
                        rule_code="RULE_EVAL_INCOMPLETE_PENALTY",
                        evidence_id=_credit_evidence_id(f"incomplete-{category.value}"),
                        description="Runtime evaluation was not completed due to build or startup failure",
                        points=Decimal("25.0"),
                        confidence=1.0,
                        calculated_delta=Decimal("-25.0"),
                    )
                    effective_deductions.append(incomplete_ded)
                    dim_ded_sum += Decimal("25.0")
                    final_dim_score = max(
                        Decimal("0.0"), round_points(final_dim_score - Decimal("25.0"))
                    )

            dim_results[category.value] = DimensionScoreResult(
                dimension_name=spec.name,
                category=category,
                weight=spec.weight,
                base_score=Decimal("100.0"),
                score=final_dim_score,
                status=status,
                receipt=effective_deductions + category_credits,
                total_deductions=round_points(dim_ded_sum),
                total_credits=round_points(dim_cred_sum),
            )

            # Weighted sum component: w_d * S_d
            composite_accum += spec.weight * final_dim_score

        # 5. Composite Overall Score Calculation (SCORE-003)
        # Bounded mathematically by sum(w_d * S_d) where sum(w_d) == 1.00
        overall_clamped = max(Decimal("0.0"), min(Decimal("100.0"), composite_accum))
        overall_rounded = round_points(overall_clamped)

        # 7. Letter Grade (SCORE-004)
        letter_grade = calculate_letter_grade(overall_rounded)

        return ScorecardResult(
            evaluation_id=evaluation_id,
            scoring_version=self.version,
            overall_score=overall_rounded,
            grade=letter_grade,
            dimensions=dim_results,
            total_deductions=round_points(total_all_deductions),
            total_credits=round_points(total_all_credits),
            evidence_count=len(evidence_records),
        )

    async def persist_scorecard(
        self,
        session: AsyncSession,
        scorecard: ScorecardResult,
    ) -> Score:
        """
        Atomically persist Score and ScoreDimension entities to PostgreSQL.
        Enforces SCORE-024 (Scorecard Immutability).
        """
        score_record = Score(
            evaluation_id=scorecard.evaluation_id,
            scoring_version=scorecard.scoring_version,
            overall_score=scorecard.overall_score,
            grade=scorecard.grade.value,
            total_deductions=scorecard.total_deductions,
            total_credits=scorecard.total_credits,
        )
        session.add(score_record)
        await session.flush()

        for dim in scorecard.dimensions.values():
            receipt_json = [item.model_dump(mode="json") for item in dim.receipt]
            dim_record = ScoreDimension(
                score_id=score_record.id,
                dimension_name=dim.dimension_name,
                score=dim.score,
                weight=dim.weight,
                base_score=dim.base_score,
                itemized_receipt=receipt_json,
            )
            session.add(dim_record)

        await session.flush()
        return score_record
