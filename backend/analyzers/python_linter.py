"""
Python AST security and quality rule scanner adapter (Bandit/Ruff rule subset).
Statically analyzes AST nodes for unsafe functions, injection vulnerabilities, and bad practices.
"""

import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import (
    AnalyzerCategory,
    AnalyzerMetadata,
    FindingLocation,
    NormalizedFinding,
)
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


class PythonSecurityVisitor(ast.NodeVisitor):
    """
    AST visitor inspecting call sites and nodes for security vulnerabilities.
    """

    def __init__(self, rel_path: str, lines: List[str]) -> None:
        self.rel_path = rel_path
        self.lines = lines
        self.findings: List[Dict[str, Any]] = []

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()[:200]
        return ""

    def visit_Call(self, node: ast.Call) -> None:
        lineno = getattr(node, "lineno", 1)
        snippet = self._get_snippet(lineno)

        # 1. eval() / exec()
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            self.findings.append(
                {
                    "rule_id": "PY-SEC-EVAL-EXEC",
                    "cwe_id": "CWE-95",
                    "severity": SeverityLevel.HIGH,
                    "title": f"Use of dynamic code execution '{node.func.id}()'",
                    "description": f"Function '{node.func.id}()' can execute arbitrary Python code, enabling remote code execution if input is tainted.",
                    "recommendation": "Use ast.literal_eval() for safe literal parsing or avoid dynamic execution.",
                    "lineno": lineno,
                    "snippet": snippet,
                }
            )

        # 2. subprocess with shell=True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"call", "run", "Popen", "check_output"}:
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.findings.append(
                        {
                            "rule_id": "PY-SEC-SHELL-TRUE",
                            "cwe_id": "CWE-78",
                            "severity": SeverityLevel.CRITICAL,
                            "title": "Subprocess invocation with 'shell=True'",
                            "description": "Executing subprocesses through the shell enables command injection attacks when strings are concatenated.",
                            "recommendation": "Pass command arguments as an array (e.g. ['git', 'clone']) and omit 'shell=True'.",
                            "lineno": lineno,
                            "snippet": snippet,
                        }
                    )

        # 3. tempfile.mktemp()
        if isinstance(node.func, ast.Attribute) and node.func.attr == "mktemp":
            self.findings.append(
                {
                    "rule_id": "PY-SEC-INSECURE-TEMPFILE",
                    "cwe_id": "CWE-377",
                    "severity": SeverityLevel.MEDIUM,
                    "title": "Use of insecure 'tempfile.mktemp()'",
                    "description": "tempfile.mktemp() is deprecated and vulnerable to symlink race condition attacks (TOCTOU).",
                    "recommendation": "Use tempfile.NamedTemporaryFile() or tempfile.TemporaryDirectory() instead.",
                    "lineno": lineno,
                    "snippet": snippet,
                }
            )

        # 4. Insecure deserialization (pickle.loads)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"loads", "load"}:
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                self.findings.append(
                    {
                        "rule_id": "PY-SEC-UNSAFE-DESERIALIZATION",
                        "cwe_id": "CWE-502",
                        "severity": SeverityLevel.CRITICAL,
                        "title": "Insecure Deserialization via 'pickle.loads()'",
                        "description": "Deserializing untrusted pickle payloads allows arbitrary code execution via Python object reducers.",
                        "recommendation": "Use safe data serialization formats such as JSON, Protocol Buffers, or messagepack.",
                        "lineno": lineno,
                        "snippet": snippet,
                    }
                )

        # 5. Weak hashing (hashlib.md5, hashlib.sha1)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"md5", "sha1"}:
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                # Check if usedforsecurity=False is set
                is_safe = False
                for kw in node.keywords:
                    if kw.arg == "usedforsecurity" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        is_safe = True
                if not is_safe:
                    self.findings.append(
                        {
                            "rule_id": "PY-SEC-WEAK-HASHING",
                            "cwe_id": "CWE-327",
                            "severity": SeverityLevel.LOW,
                            "title": f"Use of weak hash algorithm 'hashlib.{node.func.attr}()'",
                            "description": f"MD5 and SHA-1 are cryptographically broken and vulnerable to collision attacks.",
                            "recommendation": "Use SHA-256 ('hashlib.sha256()') or pass usedforsecurity=False if purely for non-cryptographic checksumming.",
                            "lineno": lineno,
                            "snippet": snippet,
                        }
                    )

        self.generic_visit(node)


class PythonSecurityLinterAnalyzer(BaseAnalyzer):
    """
    Scans Python codebases for common security anti-patterns using static AST inspection.
    """

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="python-security-linter",
            name="Python Security Linter (Bandit Rule Engine)",
            version="1.0.0",
            category=AnalyzerCategory.SECURITY,
            target_languages=["Python"],
            description="Detects command injections, eval usage, insecure deserialization, and weak cryptography.",
        )

    def can_analyze(self, tech_stack: Dict[str, Any]) -> bool:
        langs = tech_stack.get("detected_languages", {})
        primary = tech_stack.get("primary_language", "")
        return primary == "Python" or "Python" in langs

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[NormalizedFinding]:
        findings: List[NormalizedFinding] = []
        resolved_root = snapshot_path.resolve()

        for root, dirs, files in os.walk(resolved_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"venv", "node_modules", "build", "dist"}]

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                file_path = Path(root) / filename
                rel_path = file_path.relative_to(resolved_root).as_posix()

                # Skip tests directory for security linter to reduce test-fixture noise
                if rel_path.startswith("tests/") or rel_path.startswith("test/"):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    tree = ast.parse(content, filename=rel_path)
                except Exception:
                    continue

                visitor = PythonSecurityVisitor(rel_path, lines)
                visitor.visit(tree)

                for item in visitor.findings:
                    findings.append(
                        NormalizedFinding(
                            analyzer_id="python-security-linter",
                            tool_version=self.metadata.version,
                            rule_id=item["rule_id"],
                            category=EvidenceCategory.SECURITY,
                            severity=item["severity"],
                            confidence=0.95,
                            title=item["title"],
                            description=item["description"],
                            recommendation=item["recommendation"],
                            location=FindingLocation(
                                file_path=rel_path,
                                start_line=item["lineno"],
                                end_line=item["lineno"],
                                snippet=item["snippet"],
                            ),
                            cwe_ids=[item["cwe_id"]],
                            raw_evidence={
                                "rule_id": item["rule_id"],
                                "file_path": rel_path,
                                "line_number": item["lineno"],
                            },
                        )
                    )

        return findings
