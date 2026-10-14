"""
Cryptographic secret and credential scanner adapter.
Statically detects hardcoded tokens, keys, credentials, and certificates across repository files.
"""

import os
import re
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

# High-fidelity regex patterns for credential detection
SECRET_RULES: list[tuple[str, str, re.Pattern, SeverityLevel, str]] = [
    (
        "SEC-001-GITHUB-TOKEN",
        "Hardcoded GitHub Personal Access Token",
        re.compile(r"(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})"),
        SeverityLevel.CRITICAL,
        "Remove exposed GitHub token immediately and revoke it via GitHub Security Settings.",
    ),
    (
        "SEC-002-AWS-KEY",
        "Hardcoded AWS Access Key ID",
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        SeverityLevel.CRITICAL,
        "Store AWS credentials in AWS Secrets Manager or use IAM roles rather than hardcoded strings.",
    ),
    (
        "SEC-003-PRIVATE-KEY",
        "Hardcoded Private Encryption Key",
        re.compile(r"-----BEGIN[ A-Z0-9_-]+PRIVATE KEY-----"),
        SeverityLevel.CRITICAL,
        "Remove private key from source control and store in a secure key vault.",
    ),
    (
        "SEC-004-DATABASE-URI",
        "Hardcoded Database Connection URI with Credentials",
        re.compile(r"(postgres(ql)?|mysql|mongodb(\+srv)?)://[^:\s]+:[^@\s]+@[a-zA-Z0-9_.-]+"),
        SeverityLevel.HIGH,
        "Extract database connection credentials into environment variables.",
    ),
    (
        "SEC-005-SLACK-WEBHOOK",
        "Hardcoded Slack Incoming Webhook URL",
        re.compile(r"https://hooks\.slack\.com/services/T[0-9A-Z]+/B[0-9A-Z]+/[0-9a-zA-Z]+"),
        SeverityLevel.HIGH,
        "Revoke webhook and inject via environment variables.",
    ),
    (
        "SEC-006-GENERIC-API-KEY",
        "Suspected Hardcoded API Key or Secret Assignment",
        re.compile(
            r"""(?i)(?:api_key|apikey|secret_key|client_secret|auth_token)\s*=\s*['"][0-9a-zA-Z_-]{20,}['"]"""
        ),
        SeverityLevel.HIGH,
        "Do not store plaintext API keys in source files; load them from environment configuration.",
    ),
]

IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".zip",
    ".tar",
    ".gz",
    ".pyc",
    ".lock",
    ".min.js",
    ".min.css",
    ".map",
}


class SecretScannerAnalyzer(BaseAnalyzer):
    """
    Language-agnostic scanner detecting credentials, API keys, and sensitive tokens.
    """

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="secret-scanner",
            name="Cryptographic Secret & Credential Scanner",
            version="1.0.0",
            category=AnalyzerCategory.SECRET_DETECTION,
            target_languages=["*"],
            description="Detects exposed GitHub PATs, AWS keys, private keys, database credentials, and API secrets.",
        )

    def can_analyze(self, tech_stack: dict[str, Any]) -> bool:
        return True  # Applicable across all languages and repository types

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        resolved_root = snapshot_path.resolve()

        for root, dirs, files in os.walk(resolved_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in {"venv", "node_modules", "build", "dist"}
            ]

            for filename in files:
                file_path = Path(root) / filename
                suffix = file_path.suffix.lower()

                if suffix in IGNORED_EXTENSIONS:
                    continue

                rel_path = file_path.relative_to(resolved_root).as_posix()

                try:
                    # Limit scan to files < 1MB
                    if file_path.stat().st_size > 1024 * 1024:
                        continue
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                lines = text.splitlines()

                for line_idx, line in enumerate(lines, start=1):
                    # Skip excessively long lines (e.g. minified bundles)
                    if len(line) > 1000:
                        continue

                    line_matched_specific = False
                    for rule_id, title, pattern, severity, recommendation in SECRET_RULES:
                        if rule_id == "SEC-006-GENERIC-API-KEY" and line_matched_specific:
                            continue
                        match = pattern.search(line)
                        if match:
                            if rule_id != "SEC-006-GENERIC-API-KEY":
                                line_matched_specific = True
                            # Sanitize snippet: mask the secret value partially
                            matched_secret = match.group(0)
                            masked_secret = (
                                matched_secret[:4]
                                + "*" * (len(matched_secret) - 8)
                                + matched_secret[-4:]
                                if len(matched_secret) > 8
                                else "[REDACTED_SECRET]"
                            )
                            sanitized_line = line.replace(matched_secret, masked_secret).strip()

                            is_test_or_doc = (
                                any(
                                    part.lower()
                                    in {
                                        "test",
                                        "tests",
                                        "fixtures",
                                        "test_fixtures",
                                        "__tests__",
                                        "spec",
                                        "specs",
                                        "docs",
                                        "doc",
                                    }
                                    for part in Path(rel_path).parts[:-1]
                                )
                                or filename.lower().startswith("test_")
                                or filename.lower().endswith(
                                    ("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts")
                                )
                                or rel_path.lower().startswith(("docs/", "doc/", "tests/", "test/"))
                            )
                            effective_severity = SeverityLevel.LOW if is_test_or_doc else severity
                            effective_title = (
                                f"[Test/Doc Context] {title} in {rel_path}"
                                if is_test_or_doc
                                else f"{title} in {rel_path}"
                            )

                            findings.append(
                                NormalizedFinding(
                                    analyzer_id="secret-scanner",
                                    tool_version=self.metadata.version,
                                    rule_id=rule_id,
                                    category=EvidenceCategory.SECURITY,
                                    severity=effective_severity,
                                    confidence=0.98 if not is_test_or_doc else 0.50,
                                    title=effective_title,
                                    description=(
                                        f"A potential sensitive credential was identified at line {line_idx}. "
                                        "Hardcoded secrets in source control risk unauthorized credential exposure."
                                    ),
                                    recommendation=recommendation,
                                    location=FindingLocation(
                                        file_path=rel_path,
                                        start_line=line_idx,
                                        end_line=line_idx,
                                        snippet=sanitized_line[:200],
                                    ),
                                    cwe_ids=["CWE-798"],
                                    raw_evidence={
                                        "rule_id": rule_id,
                                        "matched_pattern": rule_id,
                                        "line_number": line_idx,
                                    },
                                )
                            )

        return findings
