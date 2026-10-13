"""
Finding normalization, deduplication, and severity ranking engine.
"""

from typing import Any

from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import SeverityLevel

SEVERITY_ORDER: dict[SeverityLevel, int] = {
    SeverityLevel.CRITICAL: 5,
    SeverityLevel.HIGH: 4,
    SeverityLevel.MEDIUM: 3,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFO: 1,
}


class FindingNormalizer:
    """
    Normalizes, deduplicates, and orders static analysis findings across all adapters.
    """

    @staticmethod
    def deduplicate(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
        """
        Deduplicate findings based on cryptographic fingerprint.
        If duplicates exist, retains the finding with highest severity and confidence.
        """
        seen: dict[str, NormalizedFinding] = {}

        for finding in findings:
            fp = finding.fingerprint
            if fp not in seen:
                seen[fp] = finding
            else:
                existing = seen[fp]
                current_score = SEVERITY_ORDER.get(finding.severity, 0) + finding.confidence
                existing_score = SEVERITY_ORDER.get(existing.severity, 0) + existing.confidence
                if current_score > existing_score:
                    seen[fp] = finding

        return list(seen.values())

    @staticmethod
    def sort_by_severity(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
        """
        Sort findings deterministically:
        Primary: Severity descending (CRITICAL -> INFO)
        Secondary: File path ascending
        Tertiary: Start line ascending
        """
        return sorted(
            findings,
            key=lambda f: (
                -SEVERITY_ORDER.get(f.severity, 0),
                f.location.file_path if f.location else "",
                f.location.start_line if f.location and f.location.start_line else 0,
            ),
        )

    @staticmethod
    def summarize(findings: list[NormalizedFinding]) -> dict[str, Any]:
        """
        Generate aggregate telemetry counts across severities and categories.
        """
        by_severity = {s.value: 0 for s in SeverityLevel}
        by_category: dict[str, int] = {}

        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            cat_val = f.category.value
            by_category[cat_val] = by_category.get(cat_val, 0) + 1

        return {
            "total_findings": len(findings),
            "by_severity": by_severity,
            "by_category": by_category,
            "has_critical": by_severity.get(SeverityLevel.CRITICAL.value, 0) > 0,
            "has_high": by_severity.get(SeverityLevel.HIGH.value, 0) > 0,
        }
