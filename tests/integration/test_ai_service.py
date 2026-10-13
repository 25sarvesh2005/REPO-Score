"""
Integration tests for AIInterpretationService, graceful fallback, and database persistence.
Adheres strictly to AI-002, AI-007, AI-009, and AI-010.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.models import (
    AIAnalysisPayload,
    AIAnalysisResult,
    AIRecommendationItem,
    RecommendationPriority,
)
from backend.ai.provider import IAIProvider
from backend.ai.service import AIInterpretationService
from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import EvidenceCategory, LetterGrade, SeverityLevel
from backend.database.models import AIAnalysis, Recommendation
from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.scoring.models import DimensionScoreResult, ScorecardResult


@pytest.fixture
def sample_scorecard():
    eval_id = uuid.uuid4()
    return ScorecardResult(
        evaluation_id=eval_id,
        scoring_version="1.0.0",
        overall_score=Decimal("82.4"),
        grade=LetterGrade.B,
        dimensions={
            "SECURITY": DimensionScoreResult(
                dimension_name="Security",
                category=EvidenceCategory.SECURITY,
                weight=Decimal("0.16"),
                score=Decimal("75.0"),
            ),
            "CORRECTNESS": DimensionScoreResult(
                dimension_name="Correctness",
                category=EvidenceCategory.CORRECTNESS,
                weight=Decimal("0.18"),
                score=Decimal("90.0"),
            ),
        },
        evidence_count=2,
    )


@pytest.fixture
def sample_evidence():
    return [
        NormalizedFinding(
            id=uuid.uuid4(),
            analyzer_id="secret-scanner",
            tool_version="1.0.0",
            rule_id="SEC-001-GITHUB-TOKEN",
            category=EvidenceCategory.SECURITY,
            severity=SeverityLevel.CRITICAL,
            confidence=1.0,
            title="Hardcoded GitHub PAT",
            description="ghp_ token detected in settings",
        ),
        NormalizedFinding(
            id=uuid.uuid4(),
            analyzer_id="ast-metrics",
            tool_version="1.0.0",
            rule_id="AST-001-COMPLEXITY",
            category=EvidenceCategory.MAINTAINABILITY,
            severity=SeverityLevel.MEDIUM,
            confidence=1.0,
            title="High Cyclomatic Complexity",
            description="Branch complexity 28",
        ),
    ]


@pytest.mark.asyncio
async def test_ai_service_interpretation_success(sample_scorecard, sample_evidence):
    provider = AsyncMock(spec=IAIProvider)
    provider.provider_name = "ollama"
    provider.model_name = "llama3.2:3b"
    provider.is_available = AsyncMock(return_value=True)
    payload = AIAnalysisPayload(
        executive_summary="The repository is well-structured with modular architecture and passing tests across components.",
        architectural_assessment="Clean architectural layer separation with clear boundaries and loose coupling.",
        security_risk_narrative="Zero critical vulnerabilities detected.",
        top_strengths=["Passing tests", "Type safety"],
        critical_risks=["Pin dependencies"],
        recommendations=[
            AIRecommendationItem(
                title="Lock dependencies",
                category="DEPENDENCY_HEALTH",
                priority=RecommendationPriority.LOW,
                explanation="Pinning guarantees reproducible builds.",
                actionable_steps=["Pin versions"],
                related_evidence_ids=[uuid.uuid4()],
            )
        ],
    )
    provider.generate_analysis = AsyncMock(
        return_value=AIAnalysisResult(
            payload=payload,
            provider="ollama",
            model_name="llama3.2:3b",
            success=True,
        )
    )
    service = AIInterpretationService(provider=provider)

    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_frameworks=["FastAPI"],
        evaluator_category=EvaluatorCategory.WEB_API,
    )

    result = await service.interpret_evaluation(
        scorecard=sample_scorecard,
        evidence_records=sample_evidence,
        detection=det,
    )

    assert result.success is True
    assert result.is_fallback is False
    assert result.provider == "ollama"
    assert result.model_name == "llama3.2:3b"
    assert len(result.payload.executive_summary) > 50
    assert len(result.payload.architectural_assessment) > 30
    assert len(result.payload.recommendations) > 0

    # AI-002: Assert scorecard score and grade remain 100% immutable and unchanged
    assert sample_scorecard.overall_score == Decimal("82.4")
    assert sample_scorecard.grade == LetterGrade.B


@pytest.mark.asyncio
async def test_ai_service_graceful_degradation_on_failure(sample_scorecard, sample_evidence):
    failing_provider = AsyncMock(spec=IAIProvider)
    failing_provider.provider_name = "ollama"
    failing_provider.model_name = "llama3.2:3b"
    failing_provider.is_available = AsyncMock(return_value=False)
    failing_provider.generate_analysis = AsyncMock(
        return_value=AIAnalysisResult(
            payload=AIAnalysisPayload(
                executive_summary="Failed",
                architectural_assessment="Failed",
            ),
            provider="ollama",
            model_name="llama3.2:3b",
            success=False,
            error_message="Connection to Ollama refused",
            is_fallback=True,
        )
    )

    service = AIInterpretationService(provider=failing_provider)

    result = await service.interpret_evaluation(
        scorecard=sample_scorecard,
        evidence_records=sample_evidence,
    )

    # AI-009: Graceful degradation guarantees a fallback is generated without raising
    assert result.is_fallback is True
    assert "deterministic score 82.4/100.0" in result.payload.executive_summary
    assert len(result.payload.critical_risks) > 0
    # Tethered to actual evidence records
    assert any("Hardcoded GitHub PAT" in r for r in result.payload.critical_risks)


@pytest.mark.asyncio
async def test_ai_service_persistence(sample_scorecard):
    provider = AsyncMock(spec=IAIProvider)
    provider.provider_name = "ollama"
    provider.model_name = "llama3.2:3b"
    provider.is_available = AsyncMock(return_value=True)
    provider.generate_analysis = AsyncMock(
        return_value=AIAnalysisResult(
            payload=AIAnalysisPayload(
                executive_summary="Executive summary for persistence test.",
                architectural_assessment="Architectural assessment for persistence.",
            ),
            provider="ollama",
            model_name="llama3.2:3b",
            success=True,
        )
    )
    service = AIInterpretationService(provider=provider)
    result = await service.interpret_evaluation(
        scorecard=sample_scorecard,
        evidence_records=[],
    )

    added_entities = []
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add.side_effect = lambda obj: added_entities.append(obj)
    mock_session.flush.return_value = None

    analysis_db = await service.persist_analysis(
        session=mock_session,
        evaluation_id=sample_scorecard.evaluation_id,
        analysis_result=result,
    )

    assert analysis_db.evaluation_id == sample_scorecard.evaluation_id
    assert analysis_db.provider == "ollama"
    assert analysis_db.executive_summary == result.payload.executive_summary

    analyses_added = [e for e in added_entities if isinstance(e, AIAnalysis)]
    recs_added = [e for e in added_entities if isinstance(e, Recommendation)]

    assert len(analyses_added) == 1
    assert len(recs_added) == len(result.payload.recommendations)
