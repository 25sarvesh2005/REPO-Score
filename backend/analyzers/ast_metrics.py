"""
AST-based code complexity, documentation, and maintainability metrics analyzer.
Strictly inspects abstract syntax trees without executing repository code.
"""

import ast
import os
from pathlib import Path
from typing import Any

from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import (
    AnalyzerCategory,
    AnalyzerMetadata,
    FindingLocation,
    NormalizedFinding,
)
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


class ComplexityVisitor(ast.NodeVisitor):
    """
    Computes McCabe Cyclomatic Complexity and structural metrics across AST function nodes.
    """

    def __init__(self) -> None:
        self.functions: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def _analyze_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        func_name = getattr(node, "name", "<anonymous>")
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        line_count = (end_line - start_line) + 1

        # Check docstring
        docstring = ast.get_docstring(node)
        has_docstring = bool(docstring)

        # Count parameters
        args = getattr(node, "args", None)
        param_count = 0
        if args:
            param_count = len(args.args)
            if args.vararg:
                param_count += 1
            if args.kwarg:
                param_count += 1

        # Calculate cyclomatic complexity
        # Base complexity is 1, incremented for each decision point
        complexity = 1
        for child in ast.walk(node):
            if isinstance(
                child,
                (
                    ast.If,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                    ast.ExceptHandler,
                    ast.With,
                    ast.AsyncWith,
                    ast.IfExp,
                ),
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # 'and' or 'or' adds decision branches
                complexity += len(child.values) - 1

        self.functions.append(
            {
                "name": func_name,
                "start_line": start_line,
                "end_line": end_line,
                "line_count": line_count,
                "complexity": complexity,
                "param_count": param_count,
                "has_docstring": has_docstring,
            }
        )


class AstMetricsAnalyzer(BaseAnalyzer):
    """
    Analyzes Python AST structures to calculate complexity, maintainability, and code quality.
    """

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="ast-metrics",
            name="AST Complexity & Metrics Analyzer",
            version="1.0.0",
            category=AnalyzerCategory.SYNTAX_METRICS,
            target_languages=["Python"],
            description="Computes Cyclomatic complexity, function length, parameter counts, and docstring coverage.",
        )

    def can_analyze(self, tech_stack: dict[str, Any]) -> bool:
        primary = tech_stack.get("primary_language", "")
        langs = tech_stack.get("detected_languages", {})
        return primary == "Python" or "Python" in langs

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        resolved_root = snapshot_path.resolve()

        for root, dirs, files in os.walk(resolved_root):
            # Ignore hidden dirs and build artifacts
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in {"venv", "node_modules", "build", "dist"}
            ]

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                file_path = Path(root) / filename
                rel_path = file_path.relative_to(resolved_root).as_posix()

                # Read source text safely
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                try:
                    tree = ast.parse(content, filename=rel_path)
                except SyntaxError as err:
                    findings.append(
                        NormalizedFinding(
                            analyzer_id="ast-metrics",
                            tool_version=self.metadata.version,
                            rule_id="SYNTAX-PARSE-ERROR",
                            category=EvidenceCategory.MAINTAINABILITY,
                            severity=SeverityLevel.HIGH,
                            confidence=1.0,
                            title=f"Python Syntax Error in {filename}",
                            description=f"File could not be parsed: {err.msg} at line {err.lineno}",
                            recommendation="Fix Python syntax syntax error to ensure valid compilation.",
                            location=FindingLocation(
                                file_path=rel_path,
                                start_line=err.lineno or 1,
                                end_line=err.lineno or 1,
                            ),
                        )
                    )
                    continue

                # Run complexity visitor
                visitor = ComplexityVisitor()
                visitor.visit(tree)

                is_test_file = (
                    any(
                        part.lower() in {"test", "tests", "__tests__", "spec", "specs"}
                        for part in Path(rel_path).parts[:-1]
                    )
                    or filename.lower().startswith("test_")
                    or filename.lower().endswith(
                        ("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts")
                    )
                )

                crit_complexity = 30 if is_test_file else 15
                med_complexity = 20 if is_test_file else 10
                max_lines = 150 if is_test_file else 60
                max_params = 12 if is_test_file else 6

                for func in visitor.functions:
                    # 1. Cyclomatic Complexity
                    if func["complexity"] > crit_complexity:
                        findings.append(
                            NormalizedFinding(
                                analyzer_id="ast-metrics",
                                tool_version=self.metadata.version,
                                rule_id="METRIC-CYCLOMATIC-HIGH",
                                category=EvidenceCategory.MAINTAINABILITY,
                                severity=SeverityLevel.HIGH,
                                confidence=0.95,
                                title=f"High Cyclomatic Complexity in '{func['name']}' ({func['complexity']})",
                                description=(
                                    f"Function '{func['name']}' has a cyclomatic complexity of {func['complexity']}, "
                                    f"exceeding recommended threshold of {crit_complexity}. This increases testing difficulty and defect risk."
                                ),
                                recommendation="Refactor complex branching logic into smaller helper functions.",
                                location=FindingLocation(
                                    file_path=rel_path,
                                    start_line=func["start_line"],
                                    end_line=func["end_line"],
                                ),
                            )
                        )
                    elif func["complexity"] > med_complexity:
                        findings.append(
                            NormalizedFinding(
                                analyzer_id="ast-metrics",
                                tool_version=self.metadata.version,
                                rule_id="METRIC-CYCLOMATIC-MEDIUM",
                                category=EvidenceCategory.MAINTAINABILITY,
                                severity=SeverityLevel.MEDIUM,
                                confidence=0.90,
                                title=f"Moderate Cyclomatic Complexity in '{func['name']}' ({func['complexity']})",
                                description=f"Function '{func['name']}' has a cyclomatic complexity of {func['complexity']}.",
                                recommendation="Consider simplifying conditional branches.",
                                location=FindingLocation(
                                    file_path=rel_path,
                                    start_line=func["start_line"],
                                    end_line=func["end_line"],
                                ),
                            )
                        )

                    # 2. Function Length
                    if func["line_count"] > max_lines:
                        findings.append(
                            NormalizedFinding(
                                analyzer_id="ast-metrics",
                                tool_version=self.metadata.version,
                                rule_id="METRIC-FUNCTION-TOO-LONG",
                                category=EvidenceCategory.MAINTAINABILITY,
                                severity=SeverityLevel.LOW,
                                confidence=0.85,
                                title=f"Long Function '{func['name']}' ({func['line_count']} lines)",
                                description=f"Function exceeds recommended single-responsibility length threshold ({max_lines} lines).",
                                recommendation="Decompose long function into cohesive subroutines.",
                                location=FindingLocation(
                                    file_path=rel_path,
                                    start_line=func["start_line"],
                                    end_line=func["end_line"],
                                ),
                            )
                        )

                    # 3. Excessive Parameters
                    if func["param_count"] > max_params:
                        findings.append(
                            NormalizedFinding(
                                analyzer_id="ast-metrics",
                                tool_version=self.metadata.version,
                                rule_id="METRIC-TOO-MANY-PARAMS",
                                category=EvidenceCategory.MAINTAINABILITY,
                                severity=SeverityLevel.LOW,
                                confidence=0.90,
                                title=f"Too Many Parameters in '{func['name']}' ({func['param_count']} args)",
                                description=f"Function takes more than {max_params} parameters, reducing readability and maintainability.",
                                recommendation="Encapsulate related parameters into a dedicated data structure or Pydantic model.",
                                location=FindingLocation(
                                    file_path=rel_path,
                                    start_line=func["start_line"],
                                    end_line=func["start_line"],
                                ),
                            )
                        )

        return findings
