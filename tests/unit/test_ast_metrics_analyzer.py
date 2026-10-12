"""
Unit tests for AST complexity and code maintainability analyzer.
"""

from pathlib import Path
import pytest

from backend.analyzers.ast_metrics import AstMetricsAnalyzer
from backend.api.schemas.contracts import SeverityLevel


@pytest.fixture
def ast_analyzer() -> AstMetricsAnalyzer:
    return AstMetricsAnalyzer()


@pytest.mark.asyncio
async def test_detect_high_cyclomatic_complexity(tmp_path: Path, ast_analyzer: AstMetricsAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    code = """
def deeply_nested_logic(a, b, c, d, e):
    if a:
        if b:
            if c:
                return 1
            elif d:
                return 2
        elif e:
            return 3
    for i in range(10):
        while a > 0:
            if b or c:
                a -= 1
            elif d and e:
                a -= 2
    try:
        x = 1 / a
    except ZeroDivisionError:
        x = 0
    except Exception:
        x = -1
    return x
    """
    (repo / "complex.py").write_text(code, encoding="utf-8")

    result = await ast_analyzer.analyze(repo)
    assert result.success is True
    assert len(result.findings) > 0

    complexity_findings = [f for f in result.findings if "CYCLOMATIC" in f.rule_id]
    assert len(complexity_findings) >= 1
    assert complexity_findings[0].severity in {SeverityLevel.HIGH, SeverityLevel.MEDIUM}
    assert complexity_findings[0].location.file_path == "complex.py"


@pytest.mark.asyncio
async def test_detect_too_many_parameters(tmp_path: Path, ast_analyzer: AstMetricsAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    code = """
def many_args_func(p1, p2, p3, p4, p5, p6, p7, p8):
    return p1 + p2
    """
    (repo / "params.py").write_text(code, encoding="utf-8")

    result = await ast_analyzer.analyze(repo)
    assert result.success is True

    param_findings = [f for f in result.findings if f.rule_id == "METRIC-TOO-MANY-PARAMS"]
    assert len(param_findings) == 1
    assert "many_args_func" in param_findings[0].title


@pytest.mark.asyncio
async def test_handle_python_syntax_error_cleanly(tmp_path: Path, ast_analyzer: AstMetricsAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    code = "def broken_func(:\n    invalid syntax here!"
    (repo / "broken.py").write_text(code, encoding="utf-8")

    result = await ast_analyzer.analyze(repo)
    assert result.success is True
    syntax_findings = [f for f in result.findings if f.rule_id == "SYNTAX-PARSE-ERROR"]
    assert len(syntax_findings) == 1
    assert syntax_findings[0].severity == SeverityLevel.HIGH


@pytest.mark.asyncio
async def test_clean_python_code_zero_findings(tmp_path: Path, ast_analyzer: AstMetricsAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    code = """
def add(a: int, b: int) -> int:
    \"\"\"Add two integers.\"\"\"
    return a + b
    """
    (repo / "clean.py").write_text(code, encoding="utf-8")

    result = await ast_analyzer.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 0
