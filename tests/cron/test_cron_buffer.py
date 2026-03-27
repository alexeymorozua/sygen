"""Tests for the cron results buffer (agent context injection)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sygen_bot.orchestrator.observers import _save_cron_result
from sygen_bot.workspace.loader import clear_cron_results, read_cron_results


@pytest.fixture
def mock_paths(tmp_path: Path):
    """Create a mock SygenPaths with cron_results_dir pointing to tmp."""

    class _Paths:
        cron_results_dir = tmp_path / "cron_results"

    return _Paths()


class TestSaveCronResult:
    def test_saves_result(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Test Job", "result text", "ok")
        files = list(mock_paths.cron_results_dir.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "Test Job" in content
        assert "result text" in content
        assert "ok" in content

    def test_same_job_overwrites(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job", "first result", "ok")
        _save_cron_result(mock_paths, "Job", "second result", "ok")
        files = list(mock_paths.cron_results_dir.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "second result" in content
        assert "first result" not in content

    def test_different_jobs_separate_files(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job A", "result A", "ok")
        _save_cron_result(mock_paths, "Job B", "result B", "ok")
        files = list(mock_paths.cron_results_dir.glob("*.md"))
        assert len(files) == 2

    def test_contains_markdown_structure(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "My Cron", "data here", "ok")
        files = list(mock_paths.cron_results_dir.glob("*.md"))
        content = files[0].read_text()
        assert "**Job:** My Cron" in content
        assert "**Status:** ok" in content


class TestReadCronResults:
    def test_returns_empty_when_missing(self, mock_paths) -> None:
        assert read_cron_results(mock_paths) == ""

    def test_reads_single_result(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job", "content", "ok")
        result = read_cron_results(mock_paths)
        assert "Job" in result
        assert "content" in result
        assert "Latest Cron Results" in result

    def test_reads_multiple_results(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Alpha", "result alpha", "ok")
        _save_cron_result(mock_paths, "Beta", "result beta", "ok")
        result = read_cron_results(mock_paths)
        assert "Alpha" in result
        assert "result alpha" in result
        assert "Beta" in result
        assert "result beta" in result
        assert "---" in result  # separator between results


class TestClearCronResults:
    def test_clears_all_files(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job A", "content", "ok")
        _save_cron_result(mock_paths, "Job B", "content", "ok")
        clear_cron_results(mock_paths)
        assert list(mock_paths.cron_results_dir.glob("*.md")) == []

    def test_no_error_when_missing(self, mock_paths) -> None:
        clear_cron_results(mock_paths)  # should not raise

    def test_read_after_clear_returns_empty(self, mock_paths) -> None:
        _save_cron_result(mock_paths, "Job", "content", "ok")
        clear_cron_results(mock_paths)
        assert read_cron_results(mock_paths) == ""
