"""
Domain models and structured schema definitions for the AI auxiliary subsystem.
Adheres strictly to AI_ARCHITECTURE.md, ADR-005, and AI-006 through AI-010.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RecommendationPriority(str, Enum):
    """Priority tiers for actionable remediation advice."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AIRecommendationItem(BaseModel):
    """
    Actionable remediation recommendation tethered to empirical evidence.
    Adheres strictly to AI-007.
    """
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Concise, actionable remediation recommendation")
    category: str = Field(..., description="Engineering dimension (e.g. SECURITY, CORRECTNESS)")
    priority: RecommendationPriority = Field(
        default=RecommendationPriority.MEDIUM, description="Action priority tier"
    )
    explanation: str = Field(..., description="Technical rationale grounded in detected findings")
    actionable_steps: List[str] = Field(
        default_factory=list, description="Step-by-step instructions to remediate the issue"
    )
    related_evidence_ids: List[UUID] = Field(
        default_factory=list, description="Explicit links to verified Evidence record UUIDs"
    )


class AIAnalysisPayload(BaseModel):
    """
    Canonical structured output schema enforced on all LLM responses (AI-006, AI-007).
    Unstructured text or malformed JSON is strictly rejected.
    """
    model_config = ConfigDict(extra="ignore")

    executive_summary: str = Field(
        ..., description="High-level narrative synthesis of software quality and maturity (1-3 paragraphs)"
    )
    architectural_assessment: str = Field(
        ..., description="Analysis of structural design, separation of concerns, and dependency organization"
    )
    security_risk_narrative: str = Field(
        default="No critical security vulnerabilities identified in evaluated scope.",
        description="Comprehensive summary of security posture and vulnerability exposure",
    )
    runtime_failure_root_cause: Optional[str] = Field(
        default=None, description="Diagnostic explanation of build or startup failures if applicable"
    )
    top_strengths: List[str] = Field(
        default_factory=list, max_length=5, description="Key engineering strengths observed in evidence"
    )
    critical_risks: List[str] = Field(
        default_factory=list, max_length=5, description="Primary technical risks requiring immediate attention"
    )
    recommendations: List[AIRecommendationItem] = Field(
        default_factory=list, description="Prioritized actionable remediation items"
    )


class AIAnalysisResult(BaseModel):
    """
    Complete analysis result envelope containing validated payload and operational telemetry (AI-010).
    """
    model_config = ConfigDict(extra="forbid")

    payload: AIAnalysisPayload = Field(..., description="Validated structured analysis payload")
    provider: str = Field(..., description="AI provider used (ollama, mock, external)")
    model_name: str = Field(..., description="Name of LLM model executed (e.g. llama3.2:3b)")
    prompt_version: str = Field(default="1.0.0", description="Semver identifier of prompt template")
    prompt_tokens: Optional[int] = Field(default=None, description="Prompt token count if reported")
    completion_tokens: Optional[int] = Field(default=None, description="Completion token count if reported")
    tokens_consumed: Optional[int] = Field(default=None, description="Total tokens consumed")
    duration_ms: int = Field(default=0, ge=0, description="Inference execution latency in milliseconds")
    success: bool = Field(default=True, description="Whether generation and validation succeeded")
    error_message: Optional[str] = Field(default=None, description="Diagnostic message if degraded or failed")
    is_fallback: bool = Field(default=False, description="True if generated via deterministic fallback")
