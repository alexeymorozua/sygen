"""Tests for PyPI version checking and system update checks."""

from __future__ import annotations

import importlib.metadata
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from sygen_bot.infra.version import (
    ComponentUpdate,
    SystemUpdatesInfo,
    VersionInfo,
    _check_cli_tool,
    _check_pip_dep,
    _get_cli_version,
    _parse_version,
    check_pypi,
    check_system_updates,
    fetch_changelog,
    get_current_version,
)


class TestParseVersion:
    """Test dotted version string parsing."""

    def test_standard_triple(self) -> None:
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_single_digit(self) -> None:
        assert _parse_version("5") == (5,)

    def test_four_segments(self) -> None:
        assert _parse_version("1.0.0.1") == (1, 0, 0, 1)

    def test_non_numeric_suffix_stops(self) -> None:
        assert _parse_version("1.2.3a1") == (1, 2)

    def test_empty_string(self) -> None:
        assert _parse_version("") == ()

    def test_comparison_newer(self) -> None:
        assert _parse_version("2.0.0") > _parse_version("1.9.9")

    def test_comparison_equal(self) -> None:
        assert _parse_version("1.0.0") == _parse_version("1.0.0")

    def test_comparison_older(self) -> None:
        assert _parse_version("0.1.0") < _parse_version("0.2.0")

    def test_comparison_minor_bump(self) -> None:
        assert _parse_version("1.1.0") > _parse_version("1.0.99")


class TestGetCurrentVersion:
    """Test installed version detection."""

    def test_returns_installed_version(self) -> None:
        with patch("sygen_bot.infra.version.importlib.metadata.version", return_value="1.5.0"):
            assert get_current_version() == "1.5.0"

    def test_returns_fallback_when_not_installed(self) -> None:
        with patch(
            "sygen_bot.infra.version.importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError,
        ):
            assert get_current_version() == "0.0.0"


def _mock_pypi_session(
    *, status: int = 200, json_data: dict | None = None, error: Exception | None = None
) -> MagicMock:
    """Build a mock aiohttp.ClientSession for check_pypi tests.

    Handles the combined ``async with (ClientSession() as s, s.get() as r)`` pattern.
    """
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})

    @asynccontextmanager
    async def mock_get(*_args: object, **_kwargs: object) -> AsyncGenerator[MagicMock, None]:
        if error:
            raise error
        yield resp

    session = MagicMock()
    session.get = mock_get

    @asynccontextmanager
    async def mock_session_cm(**_kwargs: object) -> AsyncGenerator[MagicMock, None]:
        yield session

    return mock_session_cm


class TestCheckPypi:
    """Test PyPI API response handling."""

    async def test_returns_version_info_when_update_available(self) -> None:
        mock = _mock_pypi_session(
            json_data={"info": {"version": "2.0.0", "summary": "A great update"}}
        )

        with (
            patch("sygen_bot.infra.version.get_current_version", return_value="1.0.0"),
            patch("sygen_bot.infra.version.aiohttp.ClientSession", mock),
        ):
            result = await check_pypi()

        assert result is not None
        assert result.current == "1.0.0"
        assert result.latest == "2.0.0"
        assert result.update_available is True
        assert result.summary == "A great update"

    async def test_no_update_when_same_version(self) -> None:
        mock = _mock_pypi_session(json_data={"info": {"version": "1.0.0", "summary": "Current"}})

        with (
            patch("sygen_bot.infra.version.get_current_version", return_value="1.0.0"),
            patch("sygen_bot.infra.version.aiohttp.ClientSession", mock),
        ):
            result = await check_pypi()

        assert result is not None
        assert result.update_available is False

    async def test_returns_none_on_http_error(self) -> None:
        mock = _mock_pypi_session(status=500)

        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await check_pypi()

        assert result is None

    async def test_returns_none_on_network_error(self) -> None:
        import aiohttp

        mock = _mock_pypi_session(error=aiohttp.ClientError())

        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await check_pypi()

        assert result is None

    async def test_returns_none_on_missing_version_field(self) -> None:
        mock = _mock_pypi_session(json_data={"info": {}})

        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await check_pypi()

        assert result is None

    async def test_returns_none_on_empty_info(self) -> None:
        mock = _mock_pypi_session(json_data={})

        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await check_pypi()

        assert result is None

    async def test_fresh_mode_sets_cache_bust_headers(self) -> None:
        call_kwargs: dict[str, object] = {}
        resp = MagicMock()
        resp.status = 200
        resp.json = AsyncMock(return_value={"info": {"version": "2.0.0", "summary": "Fresh"}})

        @asynccontextmanager
        async def mock_get(*_args: object, **kwargs: object) -> AsyncGenerator[MagicMock, None]:
            call_kwargs.update(kwargs)
            yield resp

        session = MagicMock()
        session.get = mock_get

        @asynccontextmanager
        async def mock_session_cm(**_kwargs: object) -> AsyncGenerator[MagicMock, None]:
            yield session

        with (
            patch("sygen_bot.infra.version.get_current_version", return_value="1.0.0"),
            patch("sygen_bot.infra.version.aiohttp.ClientSession", mock_session_cm),
        ):
            result = await check_pypi(fresh=True)

        assert result is not None
        headers = call_kwargs.get("headers")
        params = call_kwargs.get("params")
        assert isinstance(headers, dict)
        assert isinstance(params, dict)
        assert headers.get("Cache-Control") == "no-cache"
        assert headers.get("Pragma") == "no-cache"
        assert "_" in params

    def test_version_info_is_frozen(self) -> None:
        info = VersionInfo(current="1.0.0", latest="2.0.0", update_available=True, summary="test")
        assert info.current == "1.0.0"
        assert info.update_available is True


class TestFetchChangelog:
    """Test GitHub Releases changelog fetching."""

    async def test_returns_body_for_v_prefixed_tag(self) -> None:
        mock = _mock_pypi_session(json_data={"body": "## What's new\n\n- Feature A"})
        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await fetch_changelog("1.0.0")
        assert result is not None
        assert "Feature A" in result

    async def test_returns_none_on_404(self) -> None:
        mock = _mock_pypi_session(status=404)
        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await fetch_changelog("99.0.0")
        assert result is None

    async def test_returns_none_on_network_error(self) -> None:
        import aiohttp

        mock = _mock_pypi_session(error=aiohttp.ClientError())
        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await fetch_changelog("1.0.0")
        assert result is None

    async def test_returns_none_on_empty_body(self) -> None:
        mock = _mock_pypi_session(json_data={"body": ""})
        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await fetch_changelog("1.0.0")
        assert result is None

    async def test_strips_whitespace(self) -> None:
        mock = _mock_pypi_session(json_data={"body": "  changelog text  \n\n"})
        with patch("sygen_bot.infra.version.aiohttp.ClientSession", mock):
            result = await fetch_changelog("1.0.0")
        assert result == "changelog text"


# ---------------------------------------------------------------------------
# System update checks
# ---------------------------------------------------------------------------


class TestComponentUpdate:
    """Test ComponentUpdate and SystemUpdatesInfo dataclasses."""

    def test_system_updates_empty(self) -> None:
        info = SystemUpdatesInfo()
        assert not info.has_updates
        assert info.updates == []

    def test_system_updates_with_entries(self) -> None:
        info = SystemUpdatesInfo(
            updates=[ComponentUpdate(name="claude CLI", current="2.1.0", latest="2.2.0")]
        )
        assert info.has_updates
        assert len(info.updates) == 1

    def test_component_update_fields(self) -> None:
        upd = ComponentUpdate(name="chromadb", current="1.0.0", latest="1.1.0")
        assert upd.name == "chromadb"
        assert upd.current == "1.0.0"
        assert upd.latest == "1.1.0"


class TestGetCliVersion:
    """Test CLI version detection."""

    async def test_returns_none_when_not_installed(self) -> None:
        with patch("sygen_bot.infra.version.shutil.which", return_value=None):
            result = await _get_cli_version("nonexistent")
        assert result is None

    async def test_parses_claude_version(self) -> None:
        with (
            patch("sygen_bot.infra.version.shutil.which", return_value="/usr/bin/claude"),
            patch("sygen_bot.infra.version._run_cmd", return_value="2.1.89 (Claude Code)"),
        ):
            result = await _get_cli_version("claude")
        assert result == "2.1.89"

    async def test_parses_simple_version(self) -> None:
        with (
            patch("sygen_bot.infra.version.shutil.which", return_value="/usr/bin/gemini"),
            patch("sygen_bot.infra.version._run_cmd", return_value="0.35.3"),
        ):
            result = await _get_cli_version("gemini")
        assert result == "0.35.3"

    async def test_returns_none_on_empty_output(self) -> None:
        with (
            patch("sygen_bot.infra.version.shutil.which", return_value="/usr/bin/tool"),
            patch("sygen_bot.infra.version._run_cmd", return_value=None),
        ):
            result = await _get_cli_version("tool")
        assert result is None


class TestCheckCliTool:
    """Test CLI tool update detection."""

    async def test_detects_npm_update(self) -> None:
        with (
            patch("sygen_bot.infra.version._get_cli_version", return_value="2.1.0"),
            patch("sygen_bot.infra.version._get_npm_latest", return_value="2.2.0"),
        ):
            result = await _check_cli_tool("claude", "@anthropic-ai/claude-code", None)
        assert result is not None
        assert result.current == "2.1.0"
        assert result.latest == "2.2.0"

    async def test_no_update_when_current(self) -> None:
        with (
            patch("sygen_bot.infra.version._get_cli_version", return_value="2.2.0"),
            patch("sygen_bot.infra.version._get_npm_latest", return_value="2.2.0"),
        ):
            result = await _check_cli_tool("claude", "@anthropic-ai/claude-code", None)
        assert result is None

    async def test_returns_none_when_not_installed(self) -> None:
        with patch("sygen_bot.infra.version._get_cli_version", return_value=None):
            result = await _check_cli_tool("codex", "@openai/codex", None)
        assert result is None

    async def test_falls_back_to_pypi(self) -> None:
        with (
            patch("sygen_bot.infra.version._get_cli_version", return_value="1.0.0"),
            patch("sygen_bot.infra.version._get_npm_latest", return_value=None),
            patch("sygen_bot.infra.version._get_pypi_latest", return_value="2.0.0"),
        ):
            result = await _check_cli_tool("gemini", None, "google-genai")
        assert result is not None
        assert result.latest == "2.0.0"


class TestCheckPipDep:
    """Test pip dependency update detection."""

    async def test_detects_pip_update(self) -> None:
        with (
            patch("sygen_bot.infra.version._get_pip_installed", return_value="1.0.0"),
            patch("sygen_bot.infra.version._get_pypi_latest", return_value="1.5.0"),
        ):
            result = await _check_pip_dep("chromadb", "chromadb")
        assert result is not None
        assert result.name == "chromadb"
        assert result.latest == "1.5.0"

    async def test_no_update_when_current(self) -> None:
        with (
            patch("sygen_bot.infra.version._get_pip_installed", return_value="1.5.0"),
            patch("sygen_bot.infra.version._get_pypi_latest", return_value="1.5.0"),
        ):
            result = await _check_pip_dep("chromadb", "chromadb")
        assert result is None

    async def test_returns_none_when_not_installed(self) -> None:
        with patch("sygen_bot.infra.version._get_pip_installed", return_value=None):
            result = await _check_pip_dep("chromadb", "chromadb")
        assert result is None


class TestCheckSystemUpdates:
    """Test the orchestrating check_system_updates function."""

    async def test_aggregates_all_updates(self) -> None:
        cli_update = ComponentUpdate(name="claude CLI", current="2.0.0", latest="2.1.0")
        pip_update = ComponentUpdate(name="chromadb", current="1.0.0", latest="1.1.0")

        with (
            patch("sygen_bot.infra.version._check_cli_tool", side_effect=[cli_update, None, None]),
            patch("sygen_bot.infra.version._check_pip_dep", side_effect=[pip_update, None]),
        ):
            result = await check_system_updates()

        assert result.has_updates
        assert len(result.updates) == 2

    async def test_returns_empty_when_no_updates(self) -> None:
        with (
            patch("sygen_bot.infra.version._check_cli_tool", return_value=None),
            patch("sygen_bot.infra.version._check_pip_dep", return_value=None),
        ):
            result = await check_system_updates()

        assert not result.has_updates

    async def test_handles_exceptions_gracefully(self) -> None:
        with (
            patch("sygen_bot.infra.version._check_cli_tool", side_effect=RuntimeError("boom")),
            patch("sygen_bot.infra.version._check_pip_dep", return_value=None),
        ):
            result = await check_system_updates()

        assert not result.has_updates
