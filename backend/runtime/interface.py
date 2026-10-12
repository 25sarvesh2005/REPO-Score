"""
Abstract interface contract for runtime and behavioral evaluators.
Adheres strictly to RUNTIME_ARCHITECTURE.md and ADR-009.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from backend.repository.models import TechnologyDetectionResult
from backend.runtime.models import EvaluatorType, RuntimeObservation
from backend.sandbox.interface import ISandbox


class BaseRuntimeEvaluator(ABC):
    """
    Abstract base evaluator contract for application runtime observation.
    Executes all commands strictly within the provided isolated ISandbox.
    """

    @property
    @abstractmethod
    def evaluator_type(self) -> EvaluatorType:
        """Categorical evaluator strategy identifier."""
        pass

    @abstractmethod
    def can_evaluate(self, detection: TechnologyDetectionResult) -> bool:
        """Return True if this evaluator specializes in the detected repository archetype."""
        pass

    @abstractmethod
    async def evaluate(
        self,
        sandbox: ISandbox,
        snapshot_path: Path,
        detection: TechnologyDetectionResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> RuntimeObservation:
        """
        Execute sandboxed runtime evaluation, collect telemetry and observations,
        and return the normalized RuntimeObservation record.
        """
        pass
