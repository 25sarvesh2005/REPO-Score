"""
Analyzer Registry & Execution Dispatcher.
Discovers, filters, and concurrently executes static analyzer adapters across repository snapshots.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from backend.analyzers.ast_metrics import AstMetricsAnalyzer
from backend.analyzers.dependency_scanner import DependencyVulnerabilityAnalyzer
from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import AnalyzerExecutionResult, NormalizedFinding
from backend.analyzers.normalizer import FindingNormalizer
from backend.analyzers.python_linter import PythonSecurityLinterAnalyzer
from backend.analyzers.secret_scanner import SecretScannerAnalyzer

logger = logging.getLogger(__name__)


class AnalyzerRegistry:
    """
    Central registry for managing and dispatching static analysis adapters.
    """

    def __init__(self, register_defaults: bool = True) -> None:
        self._analyzers: list[BaseAnalyzer] = []
        if register_defaults:
            self._register_default_analyzers()

    def _register_default_analyzers(self) -> None:
        self.register(AstMetricsAnalyzer())
        self.register(SecretScannerAnalyzer())
        self.register(DependencyVulnerabilityAnalyzer())
        self.register(PythonSecurityLinterAnalyzer())

    def register(self, analyzer: BaseAnalyzer) -> None:
        """Register a new analyzer adapter."""
        self._analyzers.append(analyzer)

    def get_registered_analyzers(self) -> list[BaseAnalyzer]:
        """Return list of all registered adapters."""
        return list(self._analyzers)

    def get_applicable_analyzers(self, tech_stack: dict[str, Any]) -> list[BaseAnalyzer]:
        """Filter registered analyzers that match the detected repository technology stack."""
        return [a for a in self._analyzers if a.can_analyze(tech_stack)]

    async def execute_all(
        self,
        snapshot_path: Path,
        tech_stack: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        """
        Execute all applicable adapters in parallel across the immutable snapshot.
        Normalizes and deduplicates findings before returning.

        Failure Resilience: If any individual analyzer fails or times out, its error is logged,
        and results from other analyzers are preserved.
        """
        applicable_analyzers = self.get_applicable_analyzers(tech_stack)
        if not applicable_analyzers:
            logger.info("No static analyzers applicable for detected tech stack.")
            return []

        logger.info(
            f"Dispatching {len(applicable_analyzers)} static analyzer adapters concurrently: "
            f"{[a.metadata.analyzer_id for a in applicable_analyzers]}"
        )

        start_time = time.monotonic()

        # Run all selected analyzers concurrently
        results: list[AnalyzerExecutionResult] = await asyncio.gather(
            *[analyzer.analyze(snapshot_path, context) for analyzer in applicable_analyzers],
            return_exceptions=False,
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(f"Concurrent static analysis execution completed in {elapsed_ms}ms")

        # Aggregate findings
        all_findings: list[NormalizedFinding] = []
        for res in results:
            if not res.success:
                logger.warning(
                    f"Analyzer '{res.analyzer_id}' failed: {res.error_message}",
                    extra={"analyzer_id": res.analyzer_id, "error": res.error_message},
                )
            all_findings.extend(res.findings)

        # Normalize, deduplicate, and sort
        deduped = FindingNormalizer.deduplicate(all_findings)
        sorted_findings = FindingNormalizer.sort_by_severity(deduped)

        return sorted_findings
