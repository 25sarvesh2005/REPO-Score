"""
Deterministic Scoring Rules Engine.
Adheres strictly to SCORING_ARCHITECTURE.md, ADR-004, and SCORE-005 through SCORE-020.
Enforces 100% evidence attribution; AI models cannot modify these rules.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel
from backend.scoring.models import ReceiptItem

# Base severity deduction multipliers (SCORE-005)
SEVERITY_MULTIPLIERS: dict[SeverityLevel, Decimal] = {
    SeverityLevel.CRITICAL: Decimal("25.0"),
    SeverityLevel.HIGH: Decimal("15.0"),
    SeverityLevel.MEDIUM: Decimal("8.0"),
    SeverityLevel.LOW: Decimal("3.0"),
    SeverityLevel.INFO: Decimal("0.0"),
}

# Bounded cumulative deduction caps per rule code within a dimension (ADR-004)
# Protects against saturation distortions where repeated occurrences of minor code smells
# single-handedly destroy an entire dimension.
RULE_MAX_CUMULATIVE_DEDUCTIONS: dict[str, Decimal] = {
    # Maintainability
    "RULE_MAINT_HIGH_COMPLEXITY": Decimal("25.0"),
    "RULE_MAINT_LONG_FUNCTION": Decimal("15.0"),
    "RULE_MAINT_EXCESSIVE_PARAMS": Decimal("10.0"),
    "RULE_MAINT_LINTER_ERROR": Decimal("15.0"),
    # Architecture
    "RULE_ARCH_CIRCULAR_IMPORT": Decimal("30.0"),
    "RULE_ARCH_GOD_CLASS": Decimal("25.0"),
    # Dependency Health
    "RULE_DEP_UNPINNED": Decimal("20.0"),
    "RULE_DEP_DEPRECATED": Decimal("20.0"),
    # Documentation
    "RULE_DOC_MISSING_DOCSTRING": Decimal("15.0"),
}


def round_points(value: Any) -> Decimal:
    """Deterministically quantize points to 1 decimal place."""
    dec = Decimal(str(value))
    return dec.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class EvidenceAdapter:
    """Unified wrapper around disparate evidence representations (ORM, Pydantic, dict)."""

    def __init__(self, raw: Any) -> None:
        if isinstance(raw, dict):
            self.id = UUID(str(raw.get("id"))) if raw.get("id") else None
            self.category = EvidenceCategory(raw["category"])
            self.severity = SeverityLevel(raw["severity"])
            self.confidence = float(raw.get("confidence", 1.0))
            self.title = str(raw.get("title", ""))
            self.description = str(raw.get("description", ""))
            self.rule_id = str(raw.get("rule_id", raw.get("rule_code", "")))
            self.raw_payload = raw.get("raw_payload") or {}
        else:
            self.id = getattr(raw, "id", None)
            cat = raw.category
            self.category = cat if isinstance(cat, EvidenceCategory) else EvidenceCategory(str(cat))
            sev = raw.severity
            self.severity = sev if isinstance(sev, SeverityLevel) else SeverityLevel(str(sev))
            self.confidence = float(getattr(raw, "confidence", 1.0))
            self.title = str(getattr(raw, "title", ""))
            self.description = str(getattr(raw, "description", ""))
            self.rule_id = str(getattr(raw, "rule_id", ""))
            self.raw_payload = getattr(raw, "raw_payload", {}) or {}


def evaluate_evidence_item(evidence: EvidenceAdapter) -> ReceiptItem | None:
    """
    Evaluate an atomic evidence record against domain rules, computing exact deduction/credit.
    Returns ReceiptItem or None if finding is informational or non-scoring.
    """
    if evidence.severity == SeverityLevel.INFO:
        return None

    conf_dec = Decimal(str(evidence.confidence))
    rule_code = "RULE_GENERIC_FINDING"
    base_points = Decimal("10.0")

    # 1. CORRECTNESS (SCORE-011)
    if evidence.category == EvidenceCategory.CORRECTNESS:
        if "RUN-BUILD-001" in evidence.rule_id or "Build Failed" in evidence.title:
            rule_code = "RULE_CORR_BUILD_FAIL"
            base_points = Decimal("50.0")
        elif "SYNTAX" in evidence.rule_id or "SyntaxError" in evidence.title:
            rule_code = "RULE_CORR_SYNTAX_ERROR"
            base_points = Decimal("10.0")
        elif "RUN-BOOT" in evidence.rule_id or "Startup" in evidence.title:
            rule_code = "RULE_CORR_BOOT_CRASH"
            base_points = Decimal("40.0")
        elif "RUN-TEST" in evidence.rule_id or "Test" in evidence.title:
            rule_code = "RULE_CORR_TEST_FAIL"
            base_points = Decimal("20.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("10.0"))

    # 2. SECURITY (SCORE-012)
    elif evidence.category == EvidenceCategory.SECURITY:
        if (
            "SEC-001" in evidence.rule_id
            or "SEC-002" in evidence.rule_id
            or "Secret" in evidence.title
        ):
            rule_code = "RULE_SEC_HARDCODED_SECRET"
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("25.0"))
        elif "DEP-CVE" in evidence.rule_id or "Vulnerability" in evidence.title:
            if evidence.severity == SeverityLevel.CRITICAL:
                rule_code = "RULE_SEC_CRITICAL_CVE"
                base_points = Decimal("30.0")
            elif evidence.severity == SeverityLevel.HIGH:
                rule_code = "RULE_SEC_HIGH_CVE"
                base_points = Decimal("15.0")
            elif evidence.severity == SeverityLevel.MEDIUM:
                rule_code = "RULE_SEC_MEDIUM_CVE"
                base_points = Decimal("8.0")
            else:
                rule_code = "RULE_SEC_LOW_CVE"
                base_points = Decimal("3.0")
        elif "PY-SEC" in evidence.rule_id or "OWASP" in evidence.description:
            rule_code = "RULE_SEC_OWASP_PATTERN"
            base_points = Decimal("20.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("15.0"))

    # 3. RELIABILITY (SCORE-013)
    elif evidence.category == EvidenceCategory.RELIABILITY:
        if "RUN-BOOT" in evidence.rule_id or "Startup" in evidence.title:
            rule_code = "RULE_REL_BOOT_FAILURE"
            base_points = Decimal("35.0")
        elif "RUN-EXC" in evidence.rule_id or "Unhandled Exception" in evidence.title:
            rule_code = "RULE_REL_UNHANDLED_EXCEPTION"
            base_points = Decimal("25.0")
        elif "RUN-HTTP-001" in evidence.rule_id or "High HTTP" in evidence.title:
            rule_code = "RULE_REL_HIGH_ERROR_RATE"
            base_points = Decimal("20.0")
        elif "RUN-WRK-001" in evidence.rule_id or "Zombie" in evidence.title:
            rule_code = "RULE_REL_ZOMBIE_SHUTDOWN"
            base_points = Decimal("15.0")
        elif "RUN-CLI-001" in evidence.rule_id or "CLI Tool Panicked" in evidence.title:
            rule_code = "RULE_REL_CLI_UNCLEAN_ERROR"
            base_points = Decimal("10.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("10.0"))

    # 4. TESTING (SCORE-014)
    elif evidence.category == EvidenceCategory.TESTING:
        if "NO-TEST" in evidence.rule_id or (
            "zero" in evidence.title.lower() and "test" in evidence.title.lower()
        ):
            rule_code = "RULE_TEST_NO_TEST_FILES"
            base_points = Decimal("40.0")
        elif "RUN-TEST-001" in evidence.rule_id or "Failed in Repository" in evidence.title:
            rule_code = "RULE_TEST_SUITE_FAILURES"
            base_points = Decimal("20.0")
        elif "LOW-COVERAGE" in evidence.rule_id or "coverage < 50%" in evidence.description:
            rule_code = "RULE_TEST_LOW_COVERAGE"
            base_points = Decimal("20.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("10.0"))

    # 5. MAINTAINABILITY (SCORE-015)
    elif evidence.category == EvidenceCategory.MAINTAINABILITY:
        if (
            "AST-001" in evidence.rule_id
            or "CYCLOMATIC" in evidence.rule_id
            or "Cyclomatic" in evidence.title
        ):
            rule_code = "RULE_MAINT_HIGH_COMPLEXITY"
            base_points = (
                Decimal("5.0") if evidence.severity == SeverityLevel.HIGH else Decimal("2.5")
            )
        elif (
            "AST-002" in evidence.rule_id
            or "FUNCTION-TOO-LONG" in evidence.rule_id
            or "Long Function" in evidence.title
        ):
            rule_code = "RULE_MAINT_LONG_FUNCTION"
            base_points = Decimal("2.0")
        elif "TOO-MANY-PARAMS" in evidence.rule_id or "Too Many Parameters" in evidence.title:
            rule_code = "RULE_MAINT_EXCESSIVE_PARAMS"
            base_points = Decimal("1.5")
        elif "LINT" in evidence.rule_id:
            rule_code = "RULE_MAINT_LINTER_ERROR"
            base_points = Decimal("1.0")
        elif "SYNTAX" in evidence.rule_id or "Syntax" in evidence.title:
            rule_code = "RULE_CORR_SYNTAX_ERROR"
            base_points = Decimal("10.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("5.0"))

    # 6. ARCHITECTURE (SCORE-016)
    elif evidence.category == EvidenceCategory.ARCHITECTURE:
        if "CIRCULAR" in evidence.rule_id or "Circular" in evidence.title:
            rule_code = "RULE_ARCH_CIRCULAR_IMPORT"
            base_points = Decimal("15.0")
        elif "GOD-CLASS" in evidence.rule_id:
            rule_code = "RULE_ARCH_GOD_CLASS"
            base_points = Decimal("10.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("8.0"))

    # 7. PERFORMANCE (SCORE-017)
    elif evidence.category == EvidenceCategory.PERFORMANCE:
        if "RUN-RES-001" in evidence.rule_id or "OOM" in evidence.title:
            rule_code = "RULE_PERF_OOM_KILLED"
            base_points = Decimal("35.0")
        elif "RUN-HTTP-002" in evidence.rule_id or "Latency" in evidence.title:
            rule_code = "RULE_PERF_HIGH_LATENCY"
            base_points = Decimal("15.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("10.0"))

    # 8. DEPENDENCY_HEALTH (SCORE-018)
    elif evidence.category == EvidenceCategory.DEPENDENCY_HEALTH:
        if "UNPINNED" in evidence.rule_id:
            rule_code = "RULE_DEP_UNPINNED"
            base_points = Decimal("15.0")
        elif "DEPRECATED" in evidence.rule_id:
            rule_code = "RULE_DEP_DEPRECATED"
            base_points = Decimal("10.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("8.0"))

    # 9. DOCUMENTATION (SCORE-019)
    elif evidence.category == EvidenceCategory.DOCUMENTATION:
        if "MISSING-README" in evidence.rule_id or "README" in evidence.title:
            rule_code = "RULE_DOC_MISSING_README"
            base_points = Decimal("40.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("10.0"))

    # 10. ENGINEERING_MATURITY (SCORE-020)
    elif evidence.category == EvidenceCategory.ENGINEERING_MATURITY:
        if "NO-CI" in evidence.rule_id or "CI" in evidence.title:
            rule_code = "RULE_ENG_NO_CI_WORKFLOW"
            base_points = Decimal("30.0")
        else:
            base_points = SEVERITY_MULTIPLIERS.get(evidence.severity, Decimal("10.0"))

    # Compute confidence-weighted penalty: P_i = BasePoints * Confidence (SCORE-006)
    calculated_penalty = round_points(base_points * conf_dec)

    # Ensure evidence_id is a valid UUID
    ev_id = evidence.id
    if not ev_id:
        import uuid

        ev_id = uuid.uuid4()

    return ReceiptItem(
        type="DEDUCTION",
        rule_code=rule_code,
        evidence_id=ev_id,
        description=f"{evidence.title}: {evidence.description[:150]}",
        points=base_points,
        confidence=evidence.confidence,
        calculated_delta=-calculated_penalty,
    )
