"""
Static analysis adapter and normalized findings subsystem.
"""

from backend.analyzers.ast_metrics import AstMetricsAnalyzer
from backend.analyzers.dependency_scanner import DependencyVulnerabilityAnalyzer
from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import (
    AnalyzerCategory,
    AnalyzerExecutionResult,
    AnalyzerMetadata,
    FindingLocation,
    NormalizedFinding,
)
from backend.analyzers.normalizer import FindingNormalizer
from backend.analyzers.python_linter import PythonSecurityLinterAnalyzer
from backend.analyzers.registry import AnalyzerRegistry
from backend.analyzers.secret_scanner import SecretScannerAnalyzer

__all__ = [
    "AnalyzerCategory",
    "AnalyzerExecutionResult",
    "AnalyzerMetadata",
    "AnalyzerRegistry",
    "AstMetricsAnalyzer",
    "BaseAnalyzer",
    "DependencyVulnerabilityAnalyzer",
    "FindingLocation",
    "FindingNormalizer",
    "NormalizedFinding",
    "PythonSecurityLinterAnalyzer",
    "SecretScannerAnalyzer",
]
