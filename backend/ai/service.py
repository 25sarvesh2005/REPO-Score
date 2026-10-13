"""
AI Auxiliary Interpretation Service and Orchestrator.
Adheres strictly to AI_ARCHITECTURE.md, ADR-005, and AI-001 through AI-020.
Enforces strict boundaries: AI NEVER alters scores, runs commands, or fabricates findings.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.local_provider import LocalProvider
from backend.ai.models import (
    AIAnalysisPayload,
    AIAnalysisResult,
    AIRecommendationItem,
    RecommendationPriority,
)
from backend.ai.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_analysis_prompt,
)
from backend.ai.provider import IAIProvider
from backend.core.config import settings
from backend.database.models import AIAnalysis, Recommendation
from backend.repository.models import TechnologyDetectionResult
from backend.runtime.models import RuntimeObservation
from backend.scoring.models import ScorecardResult


class AIInterpretationService:
    """
    Coordinates prompt construction, provider resolution, bounded inference,
    schema validation, graceful fallback synthesis, and database persistence.
    """

    def __init__(self, provider: IAIProvider | None = None) -> None:
        self._provider = provider or self._resolve_default_provider()

    @property
    def provider(self) -> IAIProvider:
        return self._provider

    def _resolve_default_provider(self) -> IAIProvider:
        """Resolve concrete AI provider based on environment configuration (AI-005)."""
        provider_type = settings.AI_PROVIDER.lower()

        if provider_type == "external":
            from backend.ai.external_provider import ExternalProvider

            return ExternalProvider(
                model_name=settings.AI_MODEL_NAME,
                temperature=settings.AI_TEMPERATURE,
            )
        # Default: Local Ollama provider (AI-004)
        return LocalProvider(
            base_url=settings.AI_BASE_URL,
            model_name=settings.AI_MODEL_NAME,
            temperature=settings.AI_TEMPERATURE,
        )

    def _generate_deterministic_fallback(
        self,
        scorecard: ScorecardResult,
        evidence_records: list[Any],
        runtime: RuntimeObservation | None = None,
        error_diagnostic: str | None = None,
    ) -> AIAnalysisResult:
        """
        Synthesize a deterministic, schema-compliant fallback when AI is offline or times out (AI-009).
        Guarantees that evaluation pipelines complete successfully and deterministic scores are preserved.
        """
        # Collect top negative findings
        crit_risks: list[str] = []
        recommendations: list[AIRecommendationItem] = []

        for ev in evidence_records[:5]:
            title = getattr(ev, "title", "Finding observed")
            ev_id = getattr(ev, "id", None)
            category = getattr(ev, "category", "GENERAL")
            cat_str = category.value if hasattr(category, "value") else str(category)
            crit_risks.append(f"{cat_str}: {title}")

            if ev_id:
                recommendations.append(
                    AIRecommendationItem(
                        title=f"Remediate {title}",
                        category=cat_str,
                        priority=RecommendationPriority.HIGH,
                        explanation=getattr(
                            ev, "description", "Identified during static/runtime analysis."
                        )[:200],
                        actionable_steps=[
                            "Inspect referenced source code file",
                            "Resolve detected violation",
                        ],
                        related_evidence_ids=[ev_id],
                    )
                )

        root_cause = runtime.failure_reason if (runtime and runtime.failure_code) else None
        sec_dim = scorecard.dimensions.get("SECURITY") or scorecard.dimensions.get("Security")
        sec_score_str = f"{sec_dim.score}/100.0" if sec_dim is not None else "N/A"

        fallback_payload = AIAnalysisPayload(
            executive_summary=(
                f"Automated evaluation completed with deterministic score {scorecard.overall_score}/100.0 (Grade {scorecard.grade.value}). "
                f"Evaluated across 10 engineering dimensions using {scorecard.evidence_count} evidence records. "
                "(Detailed AI qualitative narrative is unavailable due to local AI provider status)."
            ),
            architectural_assessment=(
                f"Repository achieved composite score of {scorecard.overall_score}. "
                "Dimensional review indicates primary focus areas in Correctness, Security, and Maintainability."
            ),
            security_risk_narrative=f"Security dimension evaluated at {sec_score_str}.",
            runtime_failure_root_cause=root_cause,
            top_strengths=[
                "Scorecard evaluated across all 10 core dimensions",
                f"Deterministic scoring version {scorecard.scoring_version} applied",
            ],
            critical_risks=crit_risks
            or ["Maintain ongoing continuous testing and security hygiene."],
            recommendations=recommendations,
        )

        return AIAnalysisResult(
            payload=fallback_payload,
            provider=self._provider.provider_name,
            model_name=self._provider.model_name,
            prompt_version=PROMPT_VERSION,
            duration_ms=1,
            success=False,
            error_message=error_diagnostic
            or "AI provider unavailable; deterministic fallback synthesized (AI-009).",
            is_fallback=True,
        )

    async def interpret_evaluation(
        self,
        scorecard: ScorecardResult,
        evidence_records: list[Any],
        detection: TechnologyDetectionResult | None = None,
        runtime: RuntimeObservation | None = None,
        timeout_seconds: int | None = None,
    ) -> AIAnalysisResult:
        """
        Generate grounded qualitative interpretation and prioritized recommendations.
        Enforces 60s timeout (AI-008), 1 bounded retry (AI-017), and graceful fallback (AI-009).
        """
        effective_timeout = timeout_seconds or settings.AI_TIMEOUT_SECONDS

        prompt = build_analysis_prompt(
            scorecard=scorecard,
            evidence_records=evidence_records,
            detection=detection,
            runtime=runtime,
        )

        # Attempt 1
        result = await self._provider.generate_analysis(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            timeout_seconds=effective_timeout,
        )

        # Bounded retry policy (AI-017): retry at most once on transient disconnection, never on timeout
        if not result.success and not result.is_fallback:
            if "Connection" in (result.error_message or ""):
                result = await self._provider.generate_analysis(
                    prompt=prompt,
                    system_instruction=SYSTEM_INSTRUCTION,
                    timeout_seconds=effective_timeout,
                )

        # Graceful degradation (AI-009): if provider failed, synthesize evidence-backed fallback
        if not result.success or result.is_fallback:
            result = self._generate_deterministic_fallback(
                scorecard=scorecard,
                evidence_records=evidence_records,
                runtime=runtime,
                error_diagnostic=result.error_message,
            )

        return result

    async def persist_analysis(
        self,
        session: AsyncSession,
        evaluation_id: UUID,
        analysis_result: AIAnalysisResult,
    ) -> AIAnalysis:
        """
        Persist AIAnalysis and Recommendation entities to database (AI-010).
        """
        payload = analysis_result.payload

        analysis_record = AIAnalysis(
            evaluation_id=evaluation_id,
            provider=analysis_result.provider,
            model_name=analysis_result.model_name,
            prompt_version=analysis_result.prompt_version,
            executive_summary=payload.executive_summary,
            architectural_assessment=payload.architectural_assessment,
            runtime_failure_root_cause=payload.runtime_failure_root_cause,
            security_risk_narrative=payload.security_risk_narrative,
            tokens_consumed=analysis_result.tokens_consumed,
            duration_ms=analysis_result.duration_ms,
        )
        session.add(analysis_record)
        await session.flush()

        for rec in payload.recommendations:
            rec_record = Recommendation(
                ai_analysis_id=analysis_record.id,
                title=rec.title,
                category=rec.category,
                priority=rec.priority.value
                if hasattr(rec.priority, "value")
                else str(rec.priority),
                explanation=rec.explanation,
                actionable_steps=rec.actionable_steps,
                related_evidence_ids=rec.related_evidence_ids,
            )
            session.add(rec_record)

        await session.flush()
        return analysis_record
