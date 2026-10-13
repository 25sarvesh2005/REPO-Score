"""
Integration tests for AnalyzerRegistry concurrent execution, filtering, and failure resilience.
"""

from pathlib import Path
from typing import Any

import pytest

from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import (
    AnalyzerCategory,
    AnalyzerMetadata,
    NormalizedFinding,
)
from backend.analyzers.registry import AnalyzerRegistry
from backend.api.schemas.contracts import SeverityLevel


class CrashingDummyAnalyzer(BaseAnalyzer):
    """Simulates an adapter that encounters a fatal internal error."""

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="crashing-analyzer",
            name="Crashing Test Analyzer",
            version="1.0.0",
            category=AnalyzerCategory.CODE_QUALITY,
            target_languages=["*"],
        )

    def can_analyze(self, tech_stack: dict[str, Any]) -> bool:
        return True

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        raise RuntimeError("Simulated internal analyzer crash!")


class TimeoutDummyAnalyzer(BaseAnalyzer):
    """Simulates an adapter that hangs and times out."""

    def __init__(self) -> None:
        super().__init__(timeout_seconds=1)

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="timeout-analyzer",
            name="Timeout Test Analyzer",
            version="1.0.0",
            category=AnalyzerCategory.SECURITY,
            target_languages=["*"],
        )

    def can_analyze(self, tech_stack: dict[str, Any]) -> bool:
        return True

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        import asyncio

        await asyncio.sleep(2)  # Exceeds 1s timeout
        return []


@pytest.fixture
def test_repo_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_app"
    repo.mkdir()

    # 1. File with hardcoded secret + high complexity + insecure eval
    code = """
import os

API_KEY = "AKIAIOSFODNN7EXAMPLE"

def deeply_branched(x, y, z):
    eval("x + y")
    if x > 0:
        if y > 0:
            if z > 0:
                return 1
            else:
                return 2
        elif y < -10:
            return 3
    for i in range(10):
        while x > 0:
            x -= 1
    return 0
    """
    (repo / "main.py").write_text(code, encoding="utf-8")

    # 2. Manifest with vulnerable dependency
    (repo / "requirements.txt").write_text("requests==2.28.1\n", encoding="utf-8")

    return repo


@pytest.mark.asyncio
async def test_analyzer_registry_concurrent_execution(test_repo_fixture: Path) -> None:
    registry = AnalyzerRegistry(register_defaults=True)
    tech_stack = {"primary_language": "Python", "detected_languages": {"Python": 1.0}}

    findings = await registry.execute_all(test_repo_fixture, tech_stack)

    assert len(findings) >= 3

    # Verify severity ordering: CRITICAL findings must appear first
    assert findings[0].severity in {SeverityLevel.CRITICAL, SeverityLevel.HIGH}

    rule_ids = {f.rule_id for f in findings}
    assert "SEC-002-AWS-KEY" in rule_ids  # from secret scanner
    assert "CVE-2023-32681" in rule_ids  # from dependency scanner
    assert "PY-SEC-EVAL-EXEC" in rule_ids  # from python security linter


@pytest.mark.asyncio
async def test_analyzer_registry_failure_resilience(test_repo_fixture: Path) -> None:
    """
    Invariance test: If an individual analyzer adapter crashes or times out,
    the overall pipeline MUST NOT abort, and valid findings from other adapters MUST be preserved.
    """
    registry = AnalyzerRegistry(register_defaults=True)
    registry.register(CrashingDummyAnalyzer())
    registry.register(TimeoutDummyAnalyzer())

    tech_stack = {"primary_language": "Python", "detected_languages": {"Python": 1.0}}

    findings = await registry.execute_all(test_repo_fixture, tech_stack)

    # Valid findings from default analyzers must still be present
    assert len(findings) >= 3
    rule_ids = {f.rule_id for f in findings}
    assert "SEC-002-AWS-KEY" in rule_ids
