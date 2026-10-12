"""
Unit tests for deterministic scoring rules evaluation and confidence weighting.
"""

from decimal import Decimal
import uuid
import pytest

from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel
from backend.scoring.rules import (
    EvidenceAdapter,
    evaluate_evidence_item,
)


def test_evaluate_build_failure_rule():
    finding = NormalizedFinding(
        analyzer_id="runtime-engine",
        tool_version="1.0.0",
        rule_id="RUN-BUILD-001-FAILURE",
        category=EvidenceCategory.CORRECTNESS,
        severity=SeverityLevel.CRITICAL,
        confidence=1.0,
        title="Repository Build Failed",
        description="pip install failed with non-zero exit code",
    )
    adapter = EvidenceAdapter(finding)
    receipt = evaluate_evidence_item(adapter)

    assert receipt is not None
    assert receipt.type == "DEDUCTION"
    assert receipt.rule_code == "RULE_CORR_BUILD_FAIL"
    assert receipt.points == Decimal("50.0")
    assert receipt.calculated_delta == Decimal("-50.0")


def test_evaluate_hardcoded_secret_rule():
    finding = NormalizedFinding(
        analyzer_id="secret-scanner",
        tool_version="1.0.0",
        rule_id="SEC-001-AWS-SECRET-KEY",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.CRITICAL,
        confidence=0.9,
        title="Hardcoded AWS Secret Key",
        description="High entropy string matching AWS Secret format",
    )
    adapter = EvidenceAdapter(finding)
    receipt = evaluate_evidence_item(adapter)

    assert receipt is not None
    assert receipt.rule_code == "RULE_SEC_HARDCODED_SECRET"
    assert receipt.points == Decimal("25.0")
    # Confidence weighting: 25.0 * 0.9 = 22.5
    assert receipt.calculated_delta == Decimal("-22.5")


def test_evaluate_cve_severity_scaling():
    # Critical CVE
    crit_cve = NormalizedFinding(
        analyzer_id="dependency-scanner",
        tool_version="1.0.0",
        rule_id="DEP-CVE-2023-1234",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.CRITICAL,
        confidence=1.0,
        title="Critical CVE in requests",
        description="Remote code execution vulnerability",
    )
    rec_crit = evaluate_evidence_item(EvidenceAdapter(crit_cve))
    assert rec_crit.rule_code == "RULE_SEC_CRITICAL_CVE"
    assert rec_crit.calculated_delta == Decimal("-30.0")

    # High CVE
    high_cve = NormalizedFinding(
        analyzer_id="dependency-scanner",
        tool_version="1.0.0",
        rule_id="DEP-CVE-2023-5678",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.HIGH,
        confidence=1.0,
        title="High CVE in urllib3",
        description="Information disclosure",
    )
    rec_high = evaluate_evidence_item(EvidenceAdapter(high_cve))
    assert rec_high.rule_code == "RULE_SEC_HIGH_CVE"
    assert rec_high.calculated_delta == Decimal("-15.0")

    # Medium CVE
    med_cve = NormalizedFinding(
        analyzer_id="dependency-scanner",
        tool_version="1.0.0",
        rule_id="DEP-CVE-2023-9999",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.MEDIUM,
        confidence=1.0,
        title="Medium CVE",
        description="Denial of service",
    )
    rec_med = evaluate_evidence_item(EvidenceAdapter(med_cve))
    assert rec_med.rule_code == "RULE_SEC_MEDIUM_CVE"
    assert rec_med.calculated_delta == Decimal("-8.0")


def test_evaluate_unhandled_exception_and_oom():
    # Runtime exception
    exc_finding = NormalizedFinding(
        analyzer_id="runtime-engine",
        tool_version="1.0.0",
        rule_id="RUN-EXC-001-UNHANDLED",
        category=EvidenceCategory.RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=1.0,
        title="Unhandled Exception Detected",
        description="ZeroDivisionError in handler",
    )
    rec_exc = evaluate_evidence_item(EvidenceAdapter(exc_finding))
    assert rec_exc.rule_code == "RULE_REL_UNHANDLED_EXCEPTION"
    assert rec_exc.calculated_delta == Decimal("-25.0")

    # Performance OOM
    oom_finding = NormalizedFinding(
        analyzer_id="runtime-engine",
        tool_version="1.0.0",
        rule_id="RUN-RES-001-OOM-KILLED",
        category=EvidenceCategory.PERFORMANCE,
        severity=SeverityLevel.CRITICAL,
        confidence=1.0,
        title="Process OOM Killed",
        description="Container exceeded 2048MB memory",
    )
    rec_oom = evaluate_evidence_item(EvidenceAdapter(oom_finding))
    assert rec_oom.rule_code == "RULE_PERF_OOM_KILLED"
    assert rec_oom.calculated_delta == Decimal("-35.0")


def test_info_severity_findings_produce_zero_deductions():
    info_finding = NormalizedFinding(
        analyzer_id="runtime-test",
        tool_version="1.0.0",
        rule_id="RUN-TEST-002-ALL-PASSED",
        category=EvidenceCategory.TESTING,
        severity=SeverityLevel.INFO,
        confidence=1.0,
        title="All Tests Passed",
        description="42 tests passed cleanly",
    )
    receipt = evaluate_evidence_item(EvidenceAdapter(info_finding))
    assert receipt is None
