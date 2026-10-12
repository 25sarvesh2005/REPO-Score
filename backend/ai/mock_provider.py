"""
Mock AI Provider for deterministic unit testing and offline CI execution.
Adheres strictly to AI-003 and ADR-005. Emits zero network requests.
"""

import time
from typing import Callable, Optional
import uuid

from backend.ai.models import (
    AIAnalysisPayload,
    AIAnalysisResult,
    AIRecommendationItem,
    RecommendationPriority,
)
from backend.ai.provider import IAIProvider


class MockProvider(IAIProvider):
    """
    Deterministic mock provider emitting schema-compliant structured responses
    without contacting any live inference server.
    """

    def __init__(
        self,
        model_name: str = "mock-llama3.2:3b",
        available: bool = True,
        payload_override: Optional[AIAnalysisPayload] = None,
        custom_handler: Optional[Callable[[str, str], AIAnalysisResult]] = None,
    ) -> None:
        self._model_name = model_name
        self._available = available
        self._payload_override = payload_override
        self._custom_handler = custom_handler

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    async def generate_analysis(
        self,
        prompt: str,
        system_instruction: str,
        timeout_seconds: int = 60,
    ) -> AIAnalysisResult:
        t0 = time.monotonic()

        # Custom handler override for simulating specific test cases
        if self._custom_handler:
            return self._custom_handler(prompt, system_instruction)

        # Trigger simulated timeout
        if "trigger:timeout" in prompt:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="Timeout encountered.",
                    architectural_assessment="Incomplete.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                success=False,
                error_message=f"Inference request exceeded timeout of {timeout_seconds}s",
                is_fallback=True,
            )

        # Use payload override if provided
        if self._payload_override:
            payload = self._payload_override
        else:
            # Default rich structured mock payload
            payload = AIAnalysisPayload(
                executive_summary=(
                    "The evaluated repository demonstrates a well-structured engineering architecture "
                    "with clear separation of concerns between API routing, business services, and database persistence. "
                    "Static and runtime evidence indicates high code quality and robust testing practices."
                ),
                architectural_assessment=(
                    "Adheres to modular monolith architectural principles with clean layer boundaries. "
                    "Dependency injection is consistently utilized across service layers without circular dependencies."
                ),
                security_risk_narrative=(
                    "Security audit detected zero critical hardcoded credentials or unauthenticated remote code execution paths. "
                    "Recommended practices include regular vulnerability scanning for transitive third-party dependencies."
                ),
                runtime_failure_root_cause=None,
                top_strengths=[
                    "Deterministic test suite with high pass rate and comprehensive coverage",
                    "Modular service architecture with clean boundary contracts",
                    "Strict typing and Pydantic schema validation across API contracts",
                ],
                critical_risks=[
                    "Ensure unpinned minor dependencies are locked to prevent supply chain regressions",
                ],
                recommendations=[
                    AIRecommendationItem(
                        title="Lock dependency minor versions in production manifest",
                        category="DEPENDENCY_HEALTH",
                        priority=RecommendationPriority.LOW,
                        explanation="Pinning dependencies guarantees reproducible production container builds.",
                        actionable_steps=[
                            "Inspect requirements.txt or pyproject.toml",
                            "Update version specifiers from >= to ==",
                            "Commit generated lockfile to version control",
                        ],
                        related_evidence_ids=[uuid.uuid4()],
                    )
                ],
            )

        duration_ms = int((time.monotonic() - t0) * 1000)
        return AIAnalysisResult(
            payload=payload,
            provider=self.provider_name,
            model_name=self.model_name,
            prompt_version="1.0.0",
            prompt_tokens=450,
            completion_tokens=220,
            tokens_consumed=670,
            duration_ms=max(1, duration_ms),
            success=True,
            error_message=None,
            is_fallback=False,
        )
