"""Tests for sygen_bot.skills.commands — /skill command handler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sygen_bot.config import AgentConfig, SkillMarketplaceConfig
from sygen_bot.session.key import SessionKey
from sygen_bot.skills.commands import (
    _cancel_install,
    _pending_installs,
    cmd_skill,
    handle_skill_callback,
)


def _mock_response(status_code: int = 200, json_data: object = None, content: bytes = b"") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = content
    return resp


def _make_orch(
    *,
    enabled: bool = True,
    skills_dir: Path | None = None,
    vt_key: str | None = None,
) -> MagicMock:
    orch = MagicMock()
    cfg = MagicMock(spec=AgentConfig)
    cfg.skill_marketplace = SkillMarketplaceConfig(enabled=enabled, virustotal_api_key=vt_key)
    orch._config = cfg

    paths = MagicMock()
    paths.skills_dir = skills_dir or Path("/tmp/test-skills")
    orch._paths = paths

    return orch


def _key(chat_id: int = 123) -> SessionKey:
    return SessionKey(chat_id=chat_id)


# ---------------------------------------------------------------------------
# Disabled state
# ---------------------------------------------------------------------------


class TestSkillDisabled:
    async def test_not_enabled(self):
        orch = _make_orch(enabled=False)
        result = await cmd_skill(orch, _key(), "/skill")
        assert "not enabled" in result.text.lower()


# ---------------------------------------------------------------------------
# Help / default
# ---------------------------------------------------------------------------


class TestSkillHelp:
    async def test_help_subcommand(self):
        orch = _make_orch()
        result = await cmd_skill(orch, _key(), "/skill help")
        assert "/skill search" in result.text
        assert "/skill install" in result.text

    async def test_no_subcommand_shows_help(self):
        orch = _make_orch()
        result = await cmd_skill(orch, _key(), "/skill")
        assert "/skill search" in result.text

    async def test_unknown_subcommand_shows_help(self):
        orch = _make_orch()
        result = await cmd_skill(orch, _key(), "/skill foobar")
        assert "/skill search" in result.text


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSkillSearch:
    async def test_search_no_query(self):
        orch = _make_orch()
        result = await cmd_skill(orch, _key(), "/skill search")
        assert "usage" in result.text.lower()

    async def test_search_with_results(self):
        orch = _make_orch()
        resp = _mock_response(json_data={
            "items": [
                {
                    "name": "data-tool",
                    "owner": {"login": "user1"},
                    "description": "Analyze data",
                    "html_url": "https://github.com/openclaw/data-tool",
                }
            ]
        })

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(return_value=resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await cmd_skill(orch, _key(), "/skill search data")

        assert "data-tool" in result.text
        assert result.buttons is not None

    async def test_search_no_results(self):
        orch = _make_orch()
        empty_resp = _mock_response(json_data={"items": []})

        with patch("sygen_bot.skills.clawhub.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(return_value=empty_resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await cmd_skill(orch, _key(), "/skill search nonexistent")

        assert "no skills found" in result.text.lower()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestSkillList:
    async def test_list_empty(self, tmp_path: Path):
        orch = _make_orch(skills_dir=tmp_path)
        result = await cmd_skill(orch, _key(), "/skill list")
        assert "no skills" in result.text.lower()

    async def test_list_with_skills(self, tmp_path: Path):
        (tmp_path / "my-skill").mkdir()
        orch = _make_orch(skills_dir=tmp_path)
        result = await cmd_skill(orch, _key(), "/skill list")
        assert "my-skill" in result.text


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestSkillRemove:
    async def test_remove_no_name(self):
        orch = _make_orch()
        result = await cmd_skill(orch, _key(), "/skill remove")
        assert "usage" in result.text.lower()

    async def test_remove_existing(self, tmp_path: Path):
        (tmp_path / "my-skill").mkdir()
        orch = _make_orch(skills_dir=tmp_path)
        result = await cmd_skill(orch, _key(), "/skill remove my-skill")
        assert "removed" in result.text.lower()
        assert not (tmp_path / "my-skill").exists()

    async def test_remove_nonexistent(self, tmp_path: Path):
        orch = _make_orch(skills_dir=tmp_path)
        result = await cmd_skill(orch, _key(), "/skill remove nope")
        assert "not installed" in result.text.lower()


# ---------------------------------------------------------------------------
# Callback handling
# ---------------------------------------------------------------------------


class TestCallbackHandling:
    async def test_non_skill_callback_returns_none(self):
        orch = _make_orch()
        result = await handle_skill_callback(orch, _key(), "other:data")
        assert result is None

    async def test_cancel_callback(self, tmp_path: Path):
        skill_path = tmp_path / "test-skill"
        skill_path.mkdir()
        pending_key = "123:test-skill"
        _pending_installs[pending_key] = skill_path

        result = _cancel_install(_key(123), "test-skill")
        assert "cancelled" in result.text.lower()
        assert pending_key not in _pending_installs

    async def test_cancel_expired(self):
        result = _cancel_install(_key(123), "expired-skill")
        assert "cancelled" in result.text.lower()
