"""
Unit tests for AI subsystem models, schemas, and validation.
"""

import uuid
import pytest
from pydantic import ValidationError

from backend.ai.models import (
    AIAnalysisPayload,
    AIAnalysisResult,
    AIRecommendationItem,
    RecommendationPriority,
)


def test_recommendation_priority_enum():
    assert RecommendationPriority.CRITICAL == "CRITICAL"
    assert RecommendationPriority.HIGH == "HIGH"
    assert RecommendationPriority.MEDIUM == "MEDIUM"
    assert RecommendationPriority.LOW == "LOW"


def test_ai_recommendation_item_valid():
    ev_id = uuid.uuid4()
    item = AIRecommendationItem(
        title="Remediate SQL Injection",
        category="SECURITY",
        priority=RecommendationPriority.CRITICAL,
        explanation="Detected parameter concatenation in db query",
        actionable_steps=["Use parameterized query", "Add input validation"],
        related_evidence_ids=[ev_id],
    )
    assert item.title == "Remediate SQL Injection"
    assert item.priority == RecommendationPriority.CRITICAL
    assert item.related_evidence_ids == [ev_id]


def test_ai_analysis_payload_valid():
    payload = AIAnalysisPayload(
        executive_summary="Solid Python application with strong test coverage.",
        architectural_assessment="Modular architecture with clean dependency separation.",
        security_risk_narrative="Zero hardcoded secrets detected.",
        top_strengths=["Clean test suite", "Typed models"],
        critical_risks=["Pin dependencies in requirements.txt"],
        recommendations=[
            AIRecommendationItem(
                title="Pin dependencies",
                category="DEPENDENCY_HEALTH",
                priority=RecommendationPriority.LOW,
                explanation="Unpinned packages may introduce breaking changes.",
                actionable_steps=["Update requirements.txt"],
                related_evidence_ids=[uuid.uuid4()],
            )
        ],
    )
    assert len(payload.top_strengths) == 2
    assert len(payload.recommendations) == 1
    assert payload.runtime_failure_root_cause is None


def test_ai_analysis_payload_validation_error():
    # Missing required executive_summary and architectural_assessment
    with pytest.raises(ValidationError):
        AIAnalysisPayload.model_validate({"top_strengths": ["Strong tests"]})


def test_ai_analysis_result_envelope():
    payload = AIAnalysisPayload(
        executive_summary="Summary text.",
        architectural_assessment="Architecture text.",
    )
    res = AIAnalysisResult(
        payload=payload,
        provider="ollama",
        model_name="llama3.2:3b",
        prompt_version="1.0.0",
        prompt_tokens=300,
        completion_tokens=150,
        tokens_consumed=450,
        duration_ms=850,
        success=True,
    )
    assert res.provider == "ollama"
    assert res.tokens_consumed == 450
    assert res.is_fallback is False
