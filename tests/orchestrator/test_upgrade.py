"""Tests for /upgrade Telegram command (git pull based)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from sygen_bot.orchestrator.commands import cmd_upgrade
from sygen_bot.orchestrator.core import Orchestrator


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


class TestCmdUpgrade:
    """Test /upgrade command handler (git pull logic)."""

    async def test_already_up_to_date(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(stdout="Already up to date.\n")
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert "up to date" in result.text.lower()
        assert result.buttons is None

    async def test_successful_update(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(
            stdout="Updating abc1234..def5678\nFast-forward\n src/main.py | 2 +-\n"
        )
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert "Updated" in result.text or "updated" in result.text.lower()
        assert "restart" in result.text.lower() or "/restart" in result.text

    async def test_repo_not_found(self, orch: Orchestrator) -> None:
        with _mock_git_dir_exists(False):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert "not found" in result.text.lower()

    async def test_git_pull_exception(self, orch: Orchestrator) -> None:
        with (
            _mock_git_dir_exists(True),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="git pull", timeout=30),
            ),
        ):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert "failed" in result.text.lower()

    async def test_no_buttons_on_up_to_date(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(stdout="Already up to date.\n")
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert result.buttons is None

    async def test_no_buttons_on_successful_update(self, orch: Orchestrator) -> None:
        proc = _make_completed_process(stdout="Updating abc..def\nFast-forward\n")
        with (
            _mock_git_dir_exists(True),
            patch("subprocess.run", return_value=proc),
        ):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert result.buttons is None

    async def test_no_buttons_on_error(self, orch: Orchestrator) -> None:
        with (
            _mock_git_dir_exists(True),
            patch(
                "subprocess.run",
                side_effect=OSError("git not found"),
            ),
        ):
            result = await cmd_upgrade(orch, 1, "/upgrade")

        assert "failed" in result.text.lower()
        assert result.buttons is None
