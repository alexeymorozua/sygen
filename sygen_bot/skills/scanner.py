"""Security scanner for ClawHub skills — static analysis + VirusTotal."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_VT_API_BASE = "https://www.virustotal.com/api/v3"
_VT_TIMEOUT = 10.0

# ---------------------------------------------------------------------------
# Static analysis patterns
# ---------------------------------------------------------------------------

_CRITICAL_PATTERNS: list[tuple[str, str]] = [
    (r"\beval\s*\(", "eval() — arbitrary code execution"),
    (r"\bexec\s*\(", "exec() — arbitrary code execution"),
    (r"\bcompile\s*\(", "compile() — dynamic code compilation"),
    (r"\b__import__\s*\(", "__import__() — dynamic module loading"),
    (r"\bimportlib\b", "importlib — dynamic module loading"),
    (r"\bmarshal\.loads\b", "marshal.loads — binary deserialization"),
    (r"\bpickle\.loads?\b", "pickle — unsafe deserialization"),
]

_WARNING_PATTERNS: list[tuple[str, str]] = [
    (r"\bcurl\b", "curl — external network call"),
    (r"\bwget\b", "wget — external network call"),
    (r"\brequests\.(?:get|post|put|delete|patch)\b", "requests — HTTP call"),
    (r"\bhttpx\b", "httpx — HTTP client usage"),
    (r"\burllib\b", "urllib — HTTP call"),
    (r"\bfetch\s*\(", "fetch() — network call"),
    (r"\baxios\b", "axios — HTTP client usage"),
    (r"~\/\.ssh\b|\.ssh\/", "reads ~/.ssh/ — sensitive path"),
    (r"~\/\.aws\b|\.aws\/", "reads ~/.aws/ — sensitive path"),
    (r"~\/\.env\b|\.env\b", "reads .env — sensitive path"),
    (r"\.git\/config\b", "reads .git/config — sensitive path"),
    (r"\bwallet\b", "wallet reference — sensitive path"),
    (r"\bkeychain\b", "keychain reference — sensitive path"),
    (r"\bbase64\.b64decode\b", "base64.b64decode — potential obfuscation"),
    (r"\bcodecs\.decode\b", "codecs.decode — potential obfuscation"),
    (r"\bsubprocess\b", "subprocess — shell command execution"),
    (r"\bos\.system\s*\(", "os.system() — shell command execution"),
    (r"\bos\.popen\s*\(", "os.popen() — shell command execution"),
    (r"\bshlex\b", "shlex — shell command building"),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScanFinding:
    """A single finding from static analysis."""

    file: str
    line: int | None
    pattern: str
    severity: str  # "warning" | "critical"
    description: str


@dataclass(frozen=True, slots=True)
class VTResult:
    """VirusTotal scan result for a single file."""

    sha256: str
    detections: int
    total_engines: int
    is_clean: bool


@dataclass(slots=True)
class ScanResult:
    """Aggregated scan result for a skill."""

    skill_name: str
    static_findings: list[ScanFinding] = field(default_factory=list)
    vt_results: dict[str, VTResult] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        """No critical findings and no VT detections."""
        has_critical = any(f.severity == "critical" for f in self.static_findings)
        has_detections = any(not vr.is_clean for vr in self.vt_results.values())
        return not has_critical and not has_detections

    @property
    def summary(self) -> str:
        """Human-readable summary of the scan."""
        parts: list[str] = []
        criticals = sum(1 for f in self.static_findings if f.severity == "critical")
        warnings = sum(1 for f in self.static_findings if f.severity == "warning")
        if criticals:
            parts.append(f"{criticals} critical")
        if warnings:
            parts.append(f"{warnings} warning(s)")
        if not parts:
            parts.append("clean")
        static_summary = ", ".join(parts)

        vt_summary = "skipped"
        if self.vt_results:
            total_detections = sum(vr.detections for vr in self.vt_results.values())
            max_engines = max((vr.total_engines for vr in self.vt_results.values()), default=0)
            vt_summary = f"{total_detections}/{max_engines} detections"

        return f"Static: {static_summary} | VT: {vt_summary}"


# ---------------------------------------------------------------------------
# Static analysis
# ---------------------------------------------------------------------------


def _scan_file_static(file_path: Path, rel_name: str) -> list[ScanFinding]:
    """Scan a single file for suspicious patterns."""
    findings: list[ScanFinding] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    lines = content.splitlines()
    for line_no, line in enumerate(lines, start=1):
        for pattern, description in _CRITICAL_PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    ScanFinding(
                        file=rel_name,
                        line=line_no,
                        pattern=pattern,
                        severity="critical",
                        description=description,
                    )
                )
        for pattern, description in _WARNING_PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    ScanFinding(
                        file=rel_name,
                        line=line_no,
                        pattern=pattern,
                        severity="warning",
                        description=description,
                    )
                )

    return findings


def scan_static(skill_path: Path) -> list[ScanFinding]:
    """Run static analysis on all script files in a skill directory."""
    findings: list[ScanFinding] = []
    scripts_dir = skill_path / "scripts"

    # Scan scripts/ if it exists, otherwise scan all text files in root.
    scan_dirs = [scripts_dir] if scripts_dir.is_dir() else [skill_path]

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for file_path in sorted(scan_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix in (".pyc", ".class", ".o", ".so", ".dll"):
                continue
            rel = str(file_path.relative_to(skill_path))
            findings.extend(_scan_file_static(file_path, rel))

    return findings


# ---------------------------------------------------------------------------
# VirusTotal integration
# ---------------------------------------------------------------------------


def _sha256_file(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def _check_vt_hash(
    client: httpx.AsyncClient,
    sha256: str,
    api_key: str,
) -> VTResult | None:
    """Check a single SHA-256 hash against VirusTotal."""
    try:
        resp = await client.get(
            f"{_VT_API_BASE}/files/{sha256}",
            headers={"x-apikey": api_key},
        )
        if resp.status_code == 404:
            # File not in VT database — treat as unknown/clean.
            return VTResult(sha256=sha256, detections=0, total_engines=0, is_clean=True)
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            stats: dict[str, int] = (
                data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            )
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values()) if stats else 0
            detections = malicious + suspicious
            return VTResult(
                sha256=sha256,
                detections=detections,
                total_engines=total,
                is_clean=detections == 0,
            )
        logger.warning("VT API returned %d for hash %s", resp.status_code, sha256[:16])
    except httpx.HTTPError as exc:
        logger.warning("VT API error: %s", exc)
    return None


async def scan_virustotal(
    skill_path: Path,
    api_key: str,
) -> dict[str, VTResult]:
    """Scan all script files against VirusTotal (rate-limited to 4 req/min)."""
    results: dict[str, VTResult] = {}
    scripts_dir = skill_path / "scripts"
    scan_dir = scripts_dir if scripts_dir.is_dir() else skill_path

    files_to_scan: list[tuple[str, str]] = []
    for file_path in sorted(scan_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(skill_path))
        sha = _sha256_file(file_path)
        files_to_scan.append((rel, sha))

    async with httpx.AsyncClient(timeout=_VT_TIMEOUT) as client:
        for i, (rel_name, sha256) in enumerate(files_to_scan):
            if i > 0 and i % 4 == 0:
                # Free tier: 4 requests/minute.
                await asyncio.sleep(15.0)
            result = await _check_vt_hash(client, sha256, api_key)
            if result is not None:
                results[rel_name] = result

    return results


# ---------------------------------------------------------------------------
# Combined scan
# ---------------------------------------------------------------------------


async def scan_skill(
    skill_path: Path,
    vt_api_key: str | None = None,
) -> ScanResult:
    """Run full security scan: static analysis + optional VirusTotal check."""
    name = skill_path.name
    result = ScanResult(skill_name=name)

    # Static analysis (fast, always runs).
    result.static_findings = scan_static(skill_path)

    # VirusTotal (optional, requires API key).
    if vt_api_key:
        result.vt_results = await scan_virustotal(skill_path, vt_api_key)
    else:
        logger.info("Skipping VirusTotal scan (no API key configured)")

    return result
