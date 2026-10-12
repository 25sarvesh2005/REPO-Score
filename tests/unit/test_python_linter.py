"""
Unit tests for Python security AST linter adapter.
"""

from pathlib import Path
import pytest

from backend.analyzers.python_linter import PythonSecurityLinterAnalyzer
from backend.api.schemas.contracts import SeverityLevel


@pytest.fixture
def py_linter() -> PythonSecurityLinterAnalyzer:
    return PythonSecurityLinterAnalyzer()


@pytest.mark.asyncio
async def test_detect_python_security_anti_patterns(tmp_path: Path, py_linter: PythonSecurityLinterAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    code = """
import subprocess
import pickle
import tempfile
import hashlib

def run_user_cmd(cmd):
    eval(cmd)
    subprocess.Popen(cmd, shell=True)
    tempfile.mktemp()
    data = pickle.loads(b"payload")
    h = hashlib.md5(b"test")
    """
    (repo / "insecure.py").write_text(code, encoding="utf-8")

    result = await py_linter.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 5

    rule_ids = {f.rule_id for f in result.findings}
    assert "PY-SEC-EVAL-EXEC" in rule_ids
    assert "PY-SEC-SHELL-TRUE" in rule_ids
    assert "PY-SEC-INSECURE-TEMPFILE" in rule_ids
    assert "PY-SEC-UNSAFE-DESERIALIZATION" in rule_ids
    assert "PY-SEC-WEAK-HASHING" in rule_ids

    shell_f = next(f for f in result.findings if f.rule_id == "PY-SEC-SHELL-TRUE")
    assert shell_f.severity == SeverityLevel.CRITICAL
    assert "CWE-78" in shell_f.cwe_ids


@pytest.mark.asyncio
async def test_tests_directory_skipped(tmp_path: Path, py_linter: PythonSecurityLinterAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_evil.py").write_text("eval('1+1')\n", encoding="utf-8")

    result = await py_linter.analyze(repo)
    assert result.success is True
    # Test directory is ignored for security linter to reduce test fixtures noise
    assert len(result.findings) == 0


@pytest.mark.asyncio
async def test_clean_python_code_zero_linter_findings(tmp_path: Path, py_linter: PythonSecurityLinterAnalyzer) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    code = """
import hashlib
import json

def process_data(payload: str) -> str:
    parsed = json.loads(payload)
    return hashlib.sha256(payload.encode()).hexdigest()
    """
    (repo / "safe.py").write_text(code, encoding="utf-8")

    result = await py_linter.analyze(repo)
    assert result.success is True
    assert len(result.findings) == 0
