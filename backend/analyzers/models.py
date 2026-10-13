"""
Domain models and schema definitions for static analyzer adapters and normalized findings.
"""

import hashlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


class AnalyzerCategory(str, Enum):
    """Functional classification of static analyzer tools."""

    SYNTAX_METRICS = "SYNTAX_METRICS"
    SECURITY = "SECURITY"
    CODE_QUALITY = "CODE_QUALITY"
    DEPENDENCY = "DEPENDENCY"
    TEST_STRUCTURE = "TEST_STRUCTURE"
    ARCHITECTURE = "ARCHITECTURE"
    SECRET_DETECTION = "SECRET_DETECTION"


class FindingLocation(BaseModel):
    """Precise source code coordinates for a static finding."""

    file_path: str = Field(..., description="POSIX relative path from repository snapshot root")
    start_line: int | None = Field(default=None, ge=1, description="1-indexed starting line number")
    end_line: int | None = Field(default=None, ge=1, description="1-indexed ending line number")
    start_column: int | None = Field(default=None, ge=1, description="1-indexed starting column")
    end_column: int | None = Field(default=None, ge=1, description="1-indexed ending column")
    snippet: str | None = Field(default=None, description="Sanitized source code snippet")


class NormalizedFinding(BaseModel):
    """
    Standardized finding format across all disparate static analyzer tools.
    Provides complete traceability, deterministic deduplication fingerprints, and remediation hints.
    """

    analyzer_id: str = Field(
        ..., description="Unique slug of the analyzer adapter (e.g. ast-metrics)"
    )
    tool_version: str = Field(..., description="Semver version of the underlying analysis tool")
    rule_id: str = Field(
        ..., description="Specific rule or check identifier (e.g. SEC-001-HARDCODED-SECRET)"
    )
    category: EvidenceCategory = Field(..., description="Standardized evaluation evidence category")
    severity: SeverityLevel = Field(
        ..., description="Standardized severity level (CRITICAL to INFO)"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score of detection"
    )
    title: str = Field(..., description="Concise human-readable summary of the finding")
    description: str = Field(
        ..., description="Detailed explanation of the issue and potential risk"
    )
    recommendation: str | None = Field(default=None, description="Actionable remediation guidance")
    location: FindingLocation | None = Field(
        default=None, description="Source code location if applicable"
    )
    cwe_ids: list[str] = Field(
        default_factory=list, description="Common Weakness Enumeration identifiers"
    )
    fingerprint: str = Field(
        default="", description="Cryptographic fingerprint for cross-run deduplication"
    )
    raw_evidence: dict[str, Any] | None = Field(
        default=None, description="Bounded raw tool diagnostics for auditability"
    )

    def model_post_init(self, __context: Any) -> None:
        """Compute deterministic SHA-256 fingerprint if not explicitly provided."""
        if not self.fingerprint:
            loc_str = ""
            if self.location:
                loc_str = f"{self.location.file_path}:{self.location.start_line or 0}:{self.location.end_line or 0}"
            raw_fingerprint = f"{self.analyzer_id}|{self.rule_id}|{loc_str}|{self.title}"
            self.fingerprint = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()


class AnalyzerMetadata(BaseModel):
    """Capabilities and descriptive metadata for an analyzer adapter."""

    analyzer_id: str = Field(..., description="Unique identifier slug")
    name: str = Field(..., description="Human-readable tool name")
    version: str = Field(..., description="Adapter implementation version")
    category: AnalyzerCategory = Field(..., description="Primary functional category")
    target_languages: list[str] = Field(default_factory=list, description="Supported languages")
    description: str = Field(default="", description="Tool purpose and detection scope")


class AnalyzerExecutionResult(BaseModel):
    """Result envelope emitted by an individual analyzer adapter execution."""

    analyzer_id: str = Field(..., description="Identifier of the executing adapter")
    tool_version: str = Field(..., description="Version of the executing adapter")
    success: bool = Field(..., description="True if analysis completed without fatal errors")
    findings: list[NormalizedFinding] = Field(
        default_factory=list, description="Normalized findings detected by the tool"
    )
    duration_ms: int = Field(default=0, description="Execution time in milliseconds")
    error_message: str | None = Field(default=None, description="Error diagnostics if failed")
    raw_output: str | None = Field(default=None, description="Bounded raw stdout/stderr output")
