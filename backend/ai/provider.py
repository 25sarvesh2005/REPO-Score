"""
Abstract interface protocol for pluggable AI inference providers.
Adheres strictly to AI_ARCHITECTURE.md Section 2, ADR-005, and AI-003.
"""

from abc import ABC, abstractmethod
from typing import Optional

from backend.ai.models import AIAnalysisResult


class IAIProvider(ABC):
    """
    Abstract AI provider contract. Enables seamless hot-swapping between
    self-hosted Ollama, fast test mocks, and optional external cloud LLMs.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier slug of the provider (e.g. 'ollama', 'mock', 'external')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the active underlying model (e.g. 'llama3.2:3b')."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the backing inference engine is reachable and operational."""
        pass

    @abstractmethod
    async def generate_analysis(
        self,
        prompt: str,
        system_instruction: str,
        timeout_seconds: int = 60,
    ) -> AIAnalysisResult:
        """
        Execute LLM inference and enforce structured Pydantic schema validation.
        """
        pass
