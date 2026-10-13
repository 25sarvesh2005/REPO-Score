"""
Unit tests for findings normalizer, deduplication, and severity ranking.
"""

from backend.analyzers.models import FindingLocation, NormalizedFinding
from backend.analyzers.normalizer import FindingNormalizer
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


def test_deduplicate_identical_fingerprints() -> None:
    loc = FindingLocation(file_path="src/app.py", start_line=10, end_line=10)
    f1 = NormalizedFinding(
        analyzer_id="tool-a",
        tool_version="1.0",
        rule_id="RULE-1",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.HIGH,
        confidence=0.8,
        title="SQL Injection",
        description="Vuln description",
        location=loc,
    )
    # Same fingerprint, higher confidence
    f2 = NormalizedFinding(
        analyzer_id="tool-a",
        tool_version="1.0",
        rule_id="RULE-1",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.HIGH,
        confidence=0.95,
        title="SQL Injection",
        description="Vuln description",
        location=loc,
    )

    deduped = FindingNormalizer.deduplicate([f1, f2])
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.95


def test_sort_by_severity_descending() -> None:
    f_info = NormalizedFinding(
        analyzer_id="tool",
        tool_version="1.0",
        rule_id="R1",
        category=EvidenceCategory.MAINTAINABILITY,
        severity=SeverityLevel.INFO,
        title="Info",
        description="Info desc",
    )
    f_crit = NormalizedFinding(
        analyzer_id="tool",
        tool_version="1.0",
        rule_id="R2",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.CRITICAL,
        title="Crit",
        description="Crit desc",
    )
    f_med = NormalizedFinding(
        analyzer_id="tool",
        tool_version="1.0",
        rule_id="R3",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.MEDIUM,
        title="Med",
        description="Med desc",
    )

    sorted_list = FindingNormalizer.sort_by_severity([f_info, f_crit, f_med])
    assert [f.severity for f in sorted_list] == [
        SeverityLevel.CRITICAL,
        SeverityLevel.MEDIUM,
        SeverityLevel.INFO,
    ]


def test_summarize_findings() -> None:
    f1 = NormalizedFinding(
        analyzer_id="tool",
        tool_version="1.0",
        rule_id="R1",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.CRITICAL,
        title="Crit",
        description="Desc",
    )
    f2 = NormalizedFinding(
        analyzer_id="tool",
        tool_version="1.0",
        rule_id="R2",
        category=EvidenceCategory.DEPENDENCY_HEALTH,
        severity=SeverityLevel.MEDIUM,
        title="Dep",
        description="Desc",
    )

    summary = FindingNormalizer.summarize([f1, f2])
    assert summary["total_findings"] == 2
    assert summary["has_critical"] is True
    assert summary["by_severity"]["CRITICAL"] == 1
    assert summary["by_severity"]["MEDIUM"] == 1
    assert summary["by_category"]["SECURITY"] == 1
    assert summary["by_category"]["DEPENDENCY_HEALTH"] == 1
