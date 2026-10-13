"""
Dependency vulnerability scanner adapter with embedded OSV database mapping.
Statically parses dependency manifests and flags known vulnerable packages.
"""

import json
import re
from pathlib import Path
from typing import Any, TypedDict

from packaging.version import InvalidVersion, Version

from backend.analyzers.interface import BaseAnalyzer
from backend.analyzers.models import (
    AnalyzerCategory,
    AnalyzerMetadata,
    FindingLocation,
    NormalizedFinding,
)
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


class VulnerabilityRecord(TypedDict):
    package: str
    ecosystem: str
    vulnerable_before: str
    fixed_version: str
    cve_id: str
    cwe_ids: list[str]
    severity: SeverityLevel
    title: str
    description: str


# Curated OSV vulnerability records for known CVEs
KNOWN_VULNERABILITIES: list[VulnerabilityRecord] = [
    {
        "package": "requests",
        "ecosystem": "PyPI",
        "vulnerable_before": "2.31.0",
        "fixed_version": "2.31.0",
        "cve_id": "CVE-2023-32681",
        "cwe_ids": ["CWE-200"],
        "severity": SeverityLevel.MEDIUM,
        "title": "Unintended Leak of Proxy-Authorization Header in requests",
        "description": "Requests forwards Proxy-Authorization headers to destination servers upon redirect.",
    },
    {
        "package": "urllib3",
        "ecosystem": "PyPI",
        "vulnerable_before": "1.26.18",
        "fixed_version": "1.26.18",
        "cve_id": "CVE-2023-45803",
        "cwe_ids": ["CWE-200"],
        "severity": SeverityLevel.HIGH,
        "title": "urllib3 HTTP Request Body Stripping on Redirect Bypass",
        "description": "urllib3 fails to strip HTTP request bodies when handling cross-origin redirects.",
    },
    {
        "package": "fastapi",
        "ecosystem": "PyPI",
        "vulnerable_before": "0.109.1",
        "fixed_version": "0.109.1",
        "cve_id": "CVE-2024-24762",
        "cwe_ids": ["CWE-400"],
        "severity": SeverityLevel.HIGH,
        "title": "Regular Expression Denial of Service in FastAPI multipart parser",
        "description": "A ReDoS vulnerability in python-multipart impacts FastAPI applications processing forms.",
    },
    {
        "package": "lodash",
        "ecosystem": "npm",
        "vulnerable_before": "4.17.21",
        "fixed_version": "4.17.21",
        "cve_id": "CVE-2021-23337",
        "cwe_ids": ["CWE-78"],
        "severity": SeverityLevel.HIGH,
        "title": "Command Injection in lodash.template",
        "description": "Lodash versions prior to 4.17.21 are vulnerable to command injection via template options.",
    },
    {
        "package": "express",
        "ecosystem": "npm",
        "vulnerable_before": "4.19.2",
        "fixed_version": "4.19.2",
        "cve_id": "CVE-2024-29041",
        "cwe_ids": ["CWE-601"],
        "severity": SeverityLevel.MEDIUM,
        "title": "Open Redirect via malformed URLs in Express",
        "description": "Express.js versions before 4.19.2 can allow open redirection when passing unvalidated URLs to res.location().",
    },
]


def parse_requirements_txt(content: str) -> list[tuple[str, str, int]]:
    """Parse (package_name, version, line_number) from requirements.txt."""
    dependencies: list[tuple[str, str, int]] = []
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        clean_line = line.strip().split("#")[0]
        if not clean_line or clean_line.startswith("-"):
            continue

        # Match package==1.2.3 or package>=1.2.3 or package~=1.2.3
        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*([=><~]=?)\s*([0-9a-zA-Z_.-]+)", clean_line)
        if match:
            pkg_name = match.group(1).lower()
            ver_str = match.group(3)
            dependencies.append((pkg_name, ver_str, idx))

    return dependencies


def parse_package_json(content: str) -> list[tuple[str, str, int]]:
    """Parse dependencies from package.json."""
    dependencies: list[tuple[str, str, int]] = []
    try:
        data = json.loads(content)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for pkg_name, ver_spec in deps.items():
            # Clean leading ^ or ~
            clean_ver = re.sub(r"^[\^~>=<]+", "", ver_spec).strip()
            dependencies.append((pkg_name.lower(), clean_ver, 1))
    except Exception:
        pass
    return dependencies


class DependencyVulnerabilityAnalyzer(BaseAnalyzer):
    """
    Scans project dependency manifests against known vulnerability catalogs.
    """

    @property
    def metadata(self) -> AnalyzerMetadata:
        return AnalyzerMetadata(
            analyzer_id="dependency-vulnerability-scanner",
            name="Dependency Vulnerability Scanner (OSV Catalog)",
            version="1.0.0",
            category=AnalyzerCategory.DEPENDENCY,
            target_languages=["Python", "Node.js"],
            description="Matches declared dependencies in requirements.txt and package.json against known CVE advisories.",
        )

    def can_analyze(self, tech_stack: dict[str, Any]) -> bool:
        langs = tech_stack.get("detected_languages", {})
        return "Python" in langs or "Node.js" in langs

    async def _execute_analysis(
        self,
        snapshot_path: Path,
        context: dict[str, Any] | None = None,
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        resolved_root = snapshot_path.resolve()

        # Check Python requirements.txt
        req_file = resolved_root / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8", errors="replace")
                deps = parse_requirements_txt(content)
                rel_path = "requirements.txt"

                for pkg_name, ver_str, line_idx in deps:
                    try:
                        installed_v = Version(ver_str)
                    except InvalidVersion:
                        continue

                    for adv in KNOWN_VULNERABILITIES:
                        if adv["ecosystem"] == "PyPI" and adv["package"] == pkg_name:
                            try:
                                vuln_before = Version(adv["vulnerable_before"])
                                if installed_v < vuln_before:
                                    findings.append(
                                        NormalizedFinding(
                                            analyzer_id="dependency-vulnerability-scanner",
                                            tool_version=self.metadata.version,
                                            rule_id=adv["cve_id"],
                                            category=EvidenceCategory.DEPENDENCY_HEALTH,
                                            severity=adv["severity"],
                                            confidence=0.99,
                                            title=f"Vulnerable Dependency '{pkg_name}' ({ver_str}) - {adv['cve_id']}",
                                            description=adv["description"],
                                            recommendation=f"Upgrade '{pkg_name}' to version {adv['fixed_version']} or higher.",
                                            location=FindingLocation(
                                                file_path=rel_path,
                                                start_line=line_idx,
                                                end_line=line_idx,
                                                snippet=f"{pkg_name}=={ver_str}",
                                            ),
                                            cwe_ids=adv["cwe_ids"],
                                            raw_evidence={
                                                "package": pkg_name,
                                                "installed_version": ver_str,
                                                "fixed_version": adv["fixed_version"],
                                                "cve_id": adv["cve_id"],
                                            },
                                        )
                                    )
                            except InvalidVersion:
                                continue
            except Exception:
                pass

        # Check Node.js package.json
        pkg_file = resolved_root / "package.json"
        if pkg_file.exists():
            try:
                content = pkg_file.read_text(encoding="utf-8", errors="replace")
                deps = parse_package_json(content)
                rel_path = "package.json"

                for pkg_name, ver_str, line_idx in deps:
                    try:
                        installed_v = Version(ver_str)
                    except InvalidVersion:
                        continue

                    for adv in KNOWN_VULNERABILITIES:
                        if adv["ecosystem"] == "npm" and adv["package"] == pkg_name:
                            try:
                                vuln_before = Version(adv["vulnerable_before"])
                                if installed_v < vuln_before:
                                    findings.append(
                                        NormalizedFinding(
                                            analyzer_id="dependency-vulnerability-scanner",
                                            tool_version=self.metadata.version,
                                            rule_id=adv["cve_id"],
                                            category=EvidenceCategory.DEPENDENCY_HEALTH,
                                            severity=adv["severity"],
                                            confidence=0.99,
                                            title=f"Vulnerable Dependency '{pkg_name}' ({ver_str}) - {adv['cve_id']}",
                                            description=adv["description"],
                                            recommendation=f"Upgrade '{pkg_name}' to version {adv['fixed_version']} or higher.",
                                            location=FindingLocation(
                                                file_path=rel_path,
                                                start_line=line_idx,
                                                end_line=line_idx,
                                                snippet=f'"{pkg_name}": "{ver_str}"',
                                            ),
                                            cwe_ids=adv["cwe_ids"],
                                            raw_evidence={
                                                "package": pkg_name,
                                                "installed_version": ver_str,
                                                "fixed_version": adv["fixed_version"],
                                                "cve_id": adv["cve_id"],
                                            },
                                        )
                                    )
                            except InvalidVersion:
                                continue
            except Exception:
                pass

        return findings
