"""Tests for /upgrade command (pip/pipx + git fallback)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sygen_bot.orchestrator.commands import cmd_upgrade
from sygen_bot.orchestrator.core import Orchestrator
from sygen_bot.session.key import SessionKey


def _make_completed_process(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git", "pull"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _mock_git_dir_exists(exists: bool = True):
    """Return a patcher that makes the .git dir check return *exists*."""
    original_truediv = Path.__truediv__

    def _patched_truediv(self: Path, key: str) -> Path:
        result = original_truediv(self, key)
        if key == ".git":
            mock = MagicMock(spec=Path)
            mock.is_dir.return_value = exists
            return mock
        return result

    return patch.object(Path, "__truediv__", _patched_truediv)


def _version_info(current: str = "1.0.0", latest: str = "1.0.1", update: bool = True):
    """Create a mock VersionInfo."""
    mock = MagicMock()
    mock.current = current
    mock.latest = latest
    mock.update_available = update
    return mock


class TestCmdUpgradePip:
    """Test /upgrade for pip/pipx installs."""

    @pytest.fixture(autouse=True)
    def _upgradeable(self):
        with patch(
            "sygen_bot.infra.install.detect_install_mode", return_value="pip"
        ), patch(
            "sygen_bot.infra.install.is_upgradeable", return_value=True
        ):
            yield

    async def test_already_up_to_date(self, orch: Orchestrator) -> None:
        info = _version_info(current="1.0.6", latest="1.0.6", update=False)
        with patch("sygen_bot.orchestrator.commands.check_pypi", new_callable=AsyncMock, return_value=info):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "latest" in result.text.lower() or "up to date" in result.text.lower()

    async def test_successful_upgrade(self, orch: Orchestrator) -> None:
        info = _version_info(current="1.0.6", latest="1.0.7", update=True)
        with (
            patch("sygen_bot.orchestrator.commands.check_pypi", new_callable=AsyncMock, return_value=info),
            patch(
                "sygen_bot.infra.updater.perform_upgrade_pipeline",
                new_callable=AsyncMock,
                return_value=(True, "1.0.7", "Successfully installed sygen-1.0.7"),
            ),
            patch(
                "sygen_bot.infra.version.fetch_changelog",
                new_callable=AsyncMock,
                return_value="- Fixed emoji reactions",
            ),
            patch(
                "sygen_bot.infra.updater.write_upgrade_sentinel",
            ),
        ):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "1.0.7" in result.text
        assert "/restart" in result.text
        assert "emoji" in result.text.lower()

    async def test_upgrade_failed(self, orch: Orchestrator) -> None:
        info = _version_info(current="1.0.6", latest="1.0.7", update=True)
        with (
            patch("sygen_bot.orchestrator.commands.check_pypi", new_callable=AsyncMock, return_value=info),
            patch(
                "sygen_bot.infra.updater.perform_upgrade_pipeline",
                new_callable=AsyncMock,
                return_value=(False, "1.0.6", "ERROR: pip install failed"),
            ),
        ):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "failed" in result.text.lower() or "\u274c" in result.text

    async def test_no_buttons(self, orch: Orchestrator) -> None:
        info = _version_info(current="1.0.6", latest="1.0.6", update=False)
        with patch("sygen_bot.orchestrator.commands.check_pypi", new_callable=AsyncMock, return_value=info):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert result.buttons is None


class TestCmdUpgradeGitFallback:
    """Test /upgrade for dev/source installs (git pull fallback)."""

    @pytest.fixture(autouse=True)
    def _dev_install(self):
        with patch(
            "sygen_bot.infra.install.detect_install_mode", return_value="dev"
        ), patch(
            "sygen_bot.infra.install.is_upgradeable", return_value=False
        ):
            yield

    async def test_already_up_to_date(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(stdout="Already up to date.\n")
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "up to date" in result.text.lower()

    async def test_successful_update(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(
            stdout="Updating abc1234..def5678\nFast-forward\n src/main.py | 2 +-\n"
        )
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "Updated" in result.text or "updated" in result.text.lower()
        assert "/restart" in result.text

    async def test_repo_not_found(self, orch: Orchestrator) -> None:
        with _mock_git_dir_exists(False):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "not found" in result.text.lower()

    async def test_git_pull_exception(self, orch: Orchestrator) -> None:
        with (
            _mock_git_dir_exists(True),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="git pull", timeout=30),
            ),
        ):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert "failed" in result.text.lower()

    async def test_no_buttons(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(stdout="Already up to date.\n")
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, SessionKey(chat_id=1), "/upgrade")

        assert result.buttons is None
