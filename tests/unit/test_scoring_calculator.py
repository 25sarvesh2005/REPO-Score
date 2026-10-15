"""
Unit tests for DeterministicScoringEngine calculator, clamping, and receipts.
"""

import uuid
from decimal import Decimal

from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import EvidenceCategory, LetterGrade, SeverityLevel
from backend.scoring.calculator import DeterministicScoringEngine


def test_clean_repository_perfect_score():
    engine = DeterministicScoringEngine(version="1.0.0")
    eval_id = uuid.uuid4()

    # Clean repo with positive engineering metadata
    metadata = {
        "build_successful": True,
        "startup_successful": True,
        "tests_passed": 25,
        "tests_failed": 0,
        "line_coverage_percent": 88.5,
        "clean_shutdown": True,
        "lockfile_present": True,
        "has_readme": True,
        "ci_cd_detected": ["GitHub Actions"],
    }

    scorecard = engine.compute_scorecard(eval_id, evidence_records=[], repo_metadata=metadata)

    assert scorecard.evaluation_id == eval_id
    assert scorecard.scoring_version == "1.0.0"
    # Starting 100.0 clamped to 100.0 with positive credits
    assert scorecard.overall_score == Decimal("100.0")
    assert scorecard.grade == LetterGrade.A_PLUS
    assert len(scorecard.dimensions) == 10

    # Verify all dimensions are clamped at 100.0
    for dim in scorecard.dimensions.values():
        assert dim.score == Decimal("100.0")
        assert dim.base_score == Decimal("100.0")


def test_clamping_to_zero_under_massive_deductions():
    engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    # Generate 10 critical security findings (300 points deduction)
    findings = [
        NormalizedFinding(
            analyzer_id="dependency-scanner",
            tool_version="1.0.0",
            rule_id=f"DEP-CVE-2023-CRIT-{i}",
            category=EvidenceCategory.SECURITY,
            severity=SeverityLevel.CRITICAL,
            confidence=1.0,
            title=f"Critical RCE Vulnerability {i}",
            description="Remote code execution",
        )
        for i in range(10)
    ]

    scorecard = engine.compute_scorecard(eval_id, evidence_records=findings)
    sec_dim = scorecard.dimensions[EvidenceCategory.SECURITY.value]

    # Must clamp to 0.0 (SCORE-002: cannot be negative)
    assert sec_dim.score == Decimal("0.0")
    assert sec_dim.total_deductions == Decimal("300.0")
    # Overall score reflects the 0.0 on Security (weight 0.16 -> loses 16 points)
    assert scorecard.overall_score == Decimal("84.0")
    assert scorecard.grade == LetterGrade.B


def test_critical_security_deduction_applied_deterministically():
    engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    findings = [
        NormalizedFinding(
            analyzer_id="secret-scanner",
            tool_version="1.0.0",
            rule_id="SEC-001-AWS-SECRET-KEY",
            category=EvidenceCategory.SECURITY,
            severity=SeverityLevel.CRITICAL,
            confidence=1.0,
            title="Plaintext AWS Secret Key",
            description="High entropy root key",
        )
    ]

    scorecard = engine.compute_scorecard(eval_id, evidence_records=findings)
    sec_dim = scorecard.dimensions[EvidenceCategory.SECURITY.value]
    # SEC-001 has base deduction 25.0 * 1.0 confidence -> 75.0 score
    assert sec_dim.score == Decimal("75.0")
    assert sec_dim.total_deductions == Decimal("25.0")
    # Verify transparent receipt exists and matches evidence
    sec_receipts = [r for r in sec_dim.receipt if r.type == "DEDUCTION"]
    assert len(sec_receipts) == 1
    assert sec_receipts[0].rule_code == "RULE_SEC_HARDCODED_SECRET"


def test_all_receipt_items_have_valid_evidence_attribution():
    engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    findings = [
        NormalizedFinding(
            analyzer_id="secret-scanner",
            tool_version="1.0.0",
            rule_id="SEC-001-TOKEN",
            category=EvidenceCategory.SECURITY,
            severity=SeverityLevel.CRITICAL,
            confidence=1.0,
            title="Exposed GitHub Token",
            description="ghp_ secret detected",
        ),
        NormalizedFinding(
            analyzer_id="ast-metrics",
            tool_version="1.0.0",
            rule_id="AST-001-COMPLEXITY",
            category=EvidenceCategory.MAINTAINABILITY,
            severity=SeverityLevel.MEDIUM,
            confidence=1.0,
            title="High Cyclomatic Complexity",
            description="Function complexity 32 > 25",
        ),
    ]

    metadata = {
        "has_readme": True,
        "lockfile_present": True,
    }

    scorecard = engine.compute_scorecard(eval_id, evidence_records=findings, repo_metadata=metadata)

    # Invariant SCORE-010: Every receipt item MUST have a valid UUID evidence_id
    receipt_count = 0
    for dim in scorecard.dimensions.values():
        for receipt_item in dim.receipt:
            assert isinstance(receipt_item.evidence_id, uuid.UUID)
            assert str(receipt_item.evidence_id) != ""
            receipt_count += 1

    assert receipt_count >= 4


def test_partial_evaluation_penalties_score_23():
    engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    # Build failed evaluation
    scorecard = engine.compute_scorecard(
        eval_id,
        evidence_records=[],
        partial_status="BUILD_FAILED",
    )

    # Performance and Reliability should be marked incomplete with 25pt deduction
    perf_dim = scorecard.dimensions[EvidenceCategory.PERFORMANCE.value]
    rel_dim = scorecard.dimensions[EvidenceCategory.RELIABILITY.value]

    assert perf_dim.status == "EVALUATION_INCOMPLETE"
    assert perf_dim.score == Decimal("75.0")
    assert rel_dim.status == "EVALUATION_INCOMPLETE"
    assert rel_dim.score == Decimal("75.0")


def test_contract_response_conversion():
    engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    scorecard = engine.compute_scorecard(eval_id, evidence_records=[])
    contract = scorecard.to_scorecard_response(ai_summary="High quality project")

    assert contract.evaluation_id == eval_id
    assert contract.overall_score == scorecard.overall_score
    assert contract.grade == scorecard.grade
    assert contract.ai_executive_summary == "High quality project"
    assert len(contract.dimensions) == 10


def test_bounded_rule_deductions_prevent_dimension_saturation():
    """
    Assert that repeated code smell findings are capped at RULE_MAX_CUMULATIVE_DEDUCTIONS (ADR-004)
    and do not saturate/zero out the entire Maintainability dimension.
    """
    engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    # Generate 50 high complexity findings (would otherwise deduct 50 * 5.0 = 250 points)
    findings = [
        NormalizedFinding(
            analyzer_id="ast-metrics",
            tool_version="1.0.0",
            rule_id=f"AST-001-COMPLEXITY-{i}",
            category=EvidenceCategory.MAINTAINABILITY,
            severity=SeverityLevel.HIGH,
            confidence=1.0,
            title=f"Complex Function {i}",
            description="Cyclomatic complexity 30",
        )
        for i in range(50)
    ]

    scorecard = engine.compute_scorecard(eval_id, evidence_records=findings)
    maint_dim = scorecard.dimensions[EvidenceCategory.MAINTAINABILITY.value]

    # Must be capped at exactly 25.0 points deduction
    assert maint_dim.total_deductions == Decimal("25.0")
    assert maint_dim.score == Decimal("75.0")

    # Itemized receipt entries must sum to exactly the capped deduction
    receipt_sum = sum(
        (abs(item.calculated_delta) for item in maint_dim.receipt if item.type == "DEDUCTION"),
        Decimal("0.0"),
    )
    assert receipt_sum == Decimal("25.0")
