"""
Abstract interface contract for pluggable static analyzer adapters.
"""

from abc import ABC, abstractmethod
import asyncio
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from backend.analyzers.models import (
    AnalyzerExecutionResult,
    AnalyzerMetadata,
    NormalizedFinding,
)


class BaseAnalyzer(ABC):
    """
    Abstract contract for all static analyzer tool adapters.
    
    Invariants:
    1. Adapters must never execute untrusted scripts or build hooks.
    2. Snapshots must be accessed strictly in read-only mode.
    3. Errors or crashes in an adapter must be caught and reported as explicit failure diagnostics,
       never crashing the entire evaluation pipeline.
    4. Execution must be bounded by a strict timeout ceiling.
    """

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    @property
    @abstractmethod
    def metadata(self) -> AnalyzerMetadata:
        """Return adapter capability and descriptive metadata."""
        pass

    @abstractmethod
    def can_analyze(self, tech_stack: Dict[str, Any]) -> bool:
        """
        Determine whether this adapter is applicable given the repository's detected technology stack.
        """
        pass

    @abstractmethod
    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[NormalizedFinding]:
        """
        Internal execution logic to be implemented by specific tool adapters.
        """
        pass

    async def analyze(
        self,
        snapshot_path: Path,
        context: Optional[Dict[str, Any]] = None,
    ) -> AnalyzerExecutionResult:
        """
        Safe execution template wrapping tool execution with timeout, error handling,
        and latency measurement.
        """
        meta = self.metadata
        start_time = time.monotonic()

        try:
            findings = await asyncio.wait_for(
                self._execute_analysis(snapshot_path, context),
                timeout=self.timeout_seconds,
            )
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return AnalyzerExecutionResult(
                analyzer_id=meta.analyzer_id,
                tool_version=meta.version,
                success=True,
                findings=findings,
                duration_ms=elapsed_ms,
            )

        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return AnalyzerExecutionResult(
                analyzer_id=meta.analyzer_id,
                tool_version=meta.version,
                success=False,
                findings=[],
                duration_ms=elapsed_ms,
                error_message=f"Analyzer '{meta.name}' timed out after {self.timeout_seconds}s.",
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return AnalyzerExecutionResult(
                analyzer_id=meta.analyzer_id,
                tool_version=meta.version,
                success=False,
                findings=[],
                duration_ms=elapsed_ms,
                error_message=f"Analyzer '{meta.name}' failed: {str(exc)}",
            )
