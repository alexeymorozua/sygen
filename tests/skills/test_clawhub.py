"""Tests for sygen_bot.skills.clawhub — ClawHub marketplace wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sygen_bot.skills.clawhub import (
    SkillInfo,
    SkillNotFoundError,
    download_skill,
    install_skill,
    list_installed_skills,
    remove_skill,
    search_skills,
)


def _mock_response(status_code: int = 200, json_data: object = None, content: bytes = b"") -> MagicMock:
    """Create a mock httpx.Response (sync .json(), sync .status_code)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# search_skills
# ---------------------------------------------------------------------------


class TestSearchSkills:
    async def test_empty_query_returns_empty(self):
        result = await search_skills("")
        assert result == []

    async def test_search_returns_results_from_repo_search(self):
        resp = _mock_response(json_data={
            "items": [
                {
                    "name": "data-analyzer",
                    "owner": {"login": "user123"},
                    "description": "Analyze data",
                    "html_url": "https://github.com/openclaw/data-analyzer",
                },
            ]
        })

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(return_value=resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            results = await search_skills("data")

        assert len(results) == 1
        assert results[0].name == "data-analyzer"
        assert results[0].author == "user123"

    async def test_search_falls_back_to_code_search(self):
        empty_resp = _mock_response(json_data={"items": []})
        code_resp = _mock_response(json_data={
            "items": [
                {
                    "path": "my-skill/main.py",
                    "repository": {
                        "name": "skills",
                        "owner": {"login": "openclaw"},
                        "description": "Skills monorepo",
                        "html_url": "https://github.com/openclaw/skills",
                    },
                },
            ]
        })

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[empty_resp, code_resp])
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            results = await search_skills("my-skill")

        assert len(results) == 1
        assert results[0].name == "my-skill"

    async def test_search_handles_http_error(self):
        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            results = await search_skills("test")

        assert results == []

    async def test_search_deduplicates_code_results(self):
        empty_resp = _mock_response(json_data={"items": []})
        code_resp = _mock_response(json_data={
            "items": [
                {"path": "sk/a.py", "repository": {"name": "skills", "owner": {"login": "oc"}, "description": "", "html_url": ""}},
                {"path": "sk/b.py", "repository": {"name": "skills", "owner": {"login": "oc"}, "description": "", "html_url": ""}},
            ]
        })

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[empty_resp, code_resp])
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            results = await search_skills("sk")

        assert len(results) == 1


# ---------------------------------------------------------------------------
# download_skill
# ---------------------------------------------------------------------------


class TestDownloadSkill:
    async def test_download_not_found_raises(self, tmp_path: Path):
        resp_404 = _mock_response(status_code=404)

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(return_value=resp_404)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            with pytest.raises(SkillNotFoundError):
                await download_skill("nonexistent", tmp_path)

    async def test_download_monorepo_subfolder(self, tmp_path: Path):
        tarball_404 = _mock_response(status_code=404)
        contents_resp = _mock_response(json_data=[
            {"name": "main.py", "download_url": "https://raw.example.com/main.py"},
        ])
        file_resp = _mock_response(content=b"print('hello')")

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[tarball_404, contents_resp, file_resp])
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await download_skill("my-skill", tmp_path)

        assert (result / "main.py").read_bytes() == b"print('hello')"


# ---------------------------------------------------------------------------
# install_skill
# ---------------------------------------------------------------------------


class TestInstallSkill:
    async def test_install_copies_to_skills_dir(self, tmp_path: Path):
        src = tmp_path / "src" / "my-skill"
        src.mkdir(parents=True)
        (src / "main.py").write_text("print('ok')")

        dest = tmp_path / "skills"
        dest.mkdir()

        result = await install_skill(src, dest)
        assert result == dest / "my-skill"
        assert (dest / "my-skill" / "main.py").read_text() == "print('ok')"

    async def test_install_overwrites_existing(self, tmp_path: Path):
        src = tmp_path / "src" / "sk"
        src.mkdir(parents=True)
        (src / "new.py").write_text("new")

        dest = tmp_path / "skills"
        existing = dest / "sk"
        existing.mkdir(parents=True)
        (existing / "old.py").write_text("old")

        await install_skill(src, dest)
        assert not (dest / "sk" / "old.py").exists()
        assert (dest / "sk" / "new.py").read_text() == "new"


# ---------------------------------------------------------------------------
# list_installed_skills
# ---------------------------------------------------------------------------


class TestListInstalledSkills:
    def test_empty_dir(self, tmp_path: Path):
        result = list_installed_skills(tmp_path)
        assert result == []

    def test_nonexistent_dir(self, tmp_path: Path):
        result = list_installed_skills(tmp_path / "nonexistent")
        assert result == []

    def test_lists_skill_dirs(self, tmp_path: Path):
        (tmp_path / "skill-a").mkdir()
        (tmp_path / "skill-b").mkdir()
        result = list_installed_skills(tmp_path)
        names = [s.name for s in result]
        assert "skill-a" in names
        assert "skill-b" in names

    def test_skips_hidden_dirs(self, tmp_path: Path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        result = list_installed_skills(tmp_path)
        assert len(result) == 1
        assert result[0].name == "visible"

    def test_reads_skill_md_description(self, tmp_path: Path):
        sk = tmp_path / "my-skill"
        sk.mkdir()
        (sk / "SKILL.md").write_text("# Data Analyzer\nMore details...")
        result = list_installed_skills(tmp_path)
        assert result[0].description == "Data Analyzer"

    def test_reads_package_json_description(self, tmp_path: Path):
        sk = tmp_path / "my-skill"
        sk.mkdir()
        (sk / "package.json").write_text(json.dumps({"description": "A cool skill"}))
        result = list_installed_skills(tmp_path)
        assert result[0].description == "A cool skill"


# ---------------------------------------------------------------------------
# remove_skill
# ---------------------------------------------------------------------------


class TestRemoveSkill:
    def test_remove_existing(self, tmp_path: Path):
        (tmp_path / "my-skill").mkdir()
        assert remove_skill("my-skill", tmp_path) is True
        assert not (tmp_path / "my-skill").exists()

    def test_remove_nonexistent(self, tmp_path: Path):
        assert remove_skill("nope", tmp_path) is False
