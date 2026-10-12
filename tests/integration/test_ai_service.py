"""
Integration tests for AIInterpretationService, graceful fallback, and database persistence.
Adheres strictly to AI-002, AI-007, AI-009, and AI-010.
"""

from decimal import Decimal
from unittest.mock import AsyncMock
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import EvidenceCategory, LetterGrade, SeverityLevel
from backend.ai.mock_provider import MockProvider
from backend.ai.models import AIAnalysisPayload, AIRecommendationItem, RecommendationPriority
from backend.ai.service import AIInterpretationService
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
    provider = MockProvider(model_name="mock-llama3.2")
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
    assert result.provider == "mock"
    assert result.model_name == "mock-llama3.2"
    assert len(result.payload.executive_summary) > 50
    assert len(result.payload.architectural_assessment) > 30
    assert len(result.payload.recommendations) > 0

    # AI-002: Assert scorecard score and grade remain 100% immutable and unchanged
    assert sample_scorecard.overall_score == Decimal("82.4")
    assert sample_scorecard.grade == LetterGrade.B


@pytest.mark.asyncio
async def test_ai_service_graceful_degradation_on_failure(sample_scorecard, sample_evidence):
    # Provider configured to simulate failure
    failing_provider = MockProvider(available=False)
    failing_provider._custom_handler = lambda p, s: MockProvider()._payload_override or (
        __import__("backend.ai.models", fromlist=["AIAnalysisResult"]).AIAnalysisResult(
            payload=AIAnalysisPayload(
                executive_summary="Failed",
                architectural_assessment="Failed",
            ),
            provider="mock",
            model_name="mock-engine",
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
    service = AIInterpretationService(provider=MockProvider())
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
    assert analysis_db.provider == "mock"
    assert analysis_db.executive_summary == result.payload.executive_summary

    analyses_added = [e for e in added_entities if isinstance(e, AIAnalysis)]
    recs_added = [e for e in added_entities if isinstance(e, Recommendation)]

    assert len(analyses_added) == 1
    assert len(recs_added) == len(result.payload.recommendations)
