"""Tests for the cron results buffer (agent context injection)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from sygen_bot.orchestrator.observers import _save_cron_result
from sygen_bot.workspace.loader import clear_cron_results, read_cron_results


@pytest.fixture
def mock_paths(tmp_path: Path):
    """Create a mock SygenPaths with cron_results_path pointing to tmp."""

    class _Paths:
        cron_results_path = tmp_path / "cron_results.md"

    return _Paths()


class TestSaveCronResult:
    def test_saves_result(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Test Job", "result text", "ok")
        content = mock_paths.cron_results_path.read_text()
        assert "Test Job" in content
        assert "result text" in content
        assert "ok" in content

    def test_overwrites_previous(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job 1", "first result", "ok")
        _save_cron_result(mock_paths, "Job 2", "second result", "ok")
        content = mock_paths.cron_results_path.read_text()
        assert "Job 2" in content
        assert "second result" in content
        assert "Job 1" not in content

    def test_contains_markdown_structure(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "My Cron", "data here", "ok")
        content = mock_paths.cron_results_path.read_text()
        assert content.startswith("# Latest Cron Result")
        assert "**Job:** My Cron" in content
        assert "**Status:** ok" in content


class TestReadCronResults:
    def test_returns_empty_when_missing(self, mock_paths) -> None:
        assert read_cron_results(mock_paths) == ""

    def test_reads_existing(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job", "content", "ok")
        result = read_cron_results(mock_paths)
        assert "Job" in result
        assert "content" in result


class TestClearCronResults:
    def test_clears_file(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job", "content", "ok")
        assert mock_paths.cron_results_path.exists()
        clear_cron_results(mock_paths)
        assert not mock_paths.cron_results_path.exists()

    def test_no_error_when_missing(self, mock_paths) -> None:
        clear_cron_results(mock_paths)  # should not raise

    def test_read_after_clear_returns_empty(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job", "content", "ok")
        clear_cron_results(mock_paths)
        assert read_cron_results(mock_paths) == ""
