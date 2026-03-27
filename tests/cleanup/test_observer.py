"""Tests for the file cleanup observer."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sygen_bot.cleanup.observer import CleanupObserver, _delete_old_files
from sygen_bot.config import AgentConfig, CleanupConfig
from sygen_bot.workspace.paths import SygenPaths

# -- _delete_old_files (sync helper) --


def test_delete_old_files_removes_expired(tmp_path: Path) -> None:
    old_file = tmp_path / "old.txt"
    old_file.write_text("old")
    # Backdate mtime by 40 days.
    old_mtime = time.time() - 40 * 86400
    os.utime(old_file, (old_mtime, old_mtime))

    recent_file = tmp_path / "recent.txt"
    recent_file.write_text("recent")

    deleted = _delete_old_files(tmp_path, max_age_days=30)

    assert deleted == 1
    assert not old_file.exists()
    assert recent_file.exists()


def test_delete_old_files_recurses_into_subdirectories(tmp_path: Path) -> None:
    subdir = tmp_path / "2025-01-01"
    subdir.mkdir()
    old_file = subdir / "old.txt"
    old_file.write_text("old")
    old_mtime = time.time() - 40 * 86400
    os.utime(old_file, (old_mtime, old_mtime))

    deleted = _delete_old_files(tmp_path, max_age_days=30)
    assert deleted == 1
    assert not old_file.exists()
    # Empty subdir should be pruned
    assert not subdir.exists()


def test_delete_old_files_keeps_subdir_with_recent_files(tmp_path: Path) -> None:
    subdir = tmp_path / "2025-06-01"
    subdir.mkdir()
    recent = subdir / "recent.txt"
    recent.write_text("new")

    deleted = _delete_old_files(tmp_path, max_age_days=30)
    assert deleted == 0
    assert subdir.is_dir()
    assert recent.exists()


def test_delete_old_files_nonexistent_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert _delete_old_files(missing, max_age_days=30) == 0


def test_delete_old_files_empty_dir(tmp_path: Path) -> None:
    assert _delete_old_files(tmp_path, max_age_days=30) == 0


def test_delete_old_files_all_recent(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    assert _delete_old_files(tmp_path, max_age_days=30) == 0


# -- CleanupObserver --


def _make_config(
    *,
    enabled: bool = True,
    check_hour: int = 3,
    task_days: int = 14,
    cron_results_days: int = 7,
) -> AgentConfig:
    return AgentConfig(
        cleanup=CleanupConfig(
            enabled=enabled,
            media_files_days=30,
            output_to_user_days=30,
            check_hour=check_hour,
            task_days=task_days,
            cron_results_days=cron_results_days,
        ),
    )


def _make_paths(tmp_path: Path) -> SygenPaths:
    return SygenPaths(sygen_home=tmp_path)


async def test_start_disabled_does_not_spawn_task(tmp_path: Path) -> None:
    config = _make_config(enabled=False)
    observer = CleanupObserver(config, _make_paths(tmp_path))
    await observer.start()
    assert observer._task is None
    await observer.stop()


async def test_start_and_stop(tmp_path: Path) -> None:
    config = _make_config()
    observer = CleanupObserver(config, _make_paths(tmp_path))
    await observer.start()
    assert observer._task is not None
    assert observer._running
    await observer.stop()
    assert not observer._running


async def test_execute_deletes_files(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    paths.telegram_files_dir.mkdir(parents=True, exist_ok=True)
    paths.output_to_user_dir.mkdir(parents=True, exist_ok=True)

    old_tg = paths.telegram_files_dir / "old_photo.jpg"
    old_tg.write_text("photo")
    old_out = paths.output_to_user_dir / "old_report.pdf"
    old_out.write_text("report")

    old_mtime = time.time() - 40 * 86400
    os.utime(old_tg, (old_mtime, old_mtime))
    os.utime(old_out, (old_mtime, old_mtime))

    recent_tg = paths.telegram_files_dir / "new.jpg"
    recent_tg.write_text("new")

    config = _make_config()
    observer = CleanupObserver(config, paths)
    await observer._execute()

    assert not old_tg.exists()
    assert not old_out.exists()
    assert recent_tg.exists()


async def test_maybe_run_skips_wrong_hour(tmp_path: Path) -> None:
    config = _make_config(check_hour=3)
    observer = CleanupObserver(config, _make_paths(tmp_path))

    fake_now = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)
    with patch("sygen_bot.cleanup.observer.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)  # noqa: DTZ001, PLW0108
        await observer._maybe_run()

    assert observer._last_run_date == ""


async def test_maybe_run_skips_duplicate_same_day(tmp_path: Path) -> None:
    config = _make_config(check_hour=3)
    paths = _make_paths(tmp_path)
    paths.telegram_files_dir.mkdir(parents=True, exist_ok=True)
    paths.output_to_user_dir.mkdir(parents=True, exist_ok=True)
    observer = CleanupObserver(config, paths)

    fake_now = datetime(2025, 6, 1, 3, 30, tzinfo=UTC)
    with patch("sygen_bot.cleanup.observer.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)  # noqa: DTZ001, PLW0108
        await observer._maybe_run()
        assert observer._last_run_date == "2025-06-01"

        # Second call same day: should not run again.
        await observer._maybe_run()
        assert observer._last_run_date == "2025-06-01"


# -- cron_results cleanup --


async def test_execute_cleans_old_cron_results(tmp_path: Path) -> None:
    """Old files in cron_results/ are deleted."""
    paths = _make_paths(tmp_path)
    paths.cron_results_dir.mkdir(parents=True, exist_ok=True)

    old_result = paths.cron_results_dir / "stale_job.md"
    old_result.write_text("old result")
    old_mtime = time.time() - 10 * 86400  # 10 days old
    os.utime(old_result, (old_mtime, old_mtime))

    recent_result = paths.cron_results_dir / "fresh_job.md"
    recent_result.write_text("fresh result")

    config = _make_config(cron_results_days=7)
    observer = CleanupObserver(config, paths)
    await observer._execute()

    assert not old_result.exists()
    assert recent_result.exists()


async def test_execute_keeps_recent_cron_results(tmp_path: Path) -> None:
    """Recent cron results are not deleted."""
    paths = _make_paths(tmp_path)
    paths.cron_results_dir.mkdir(parents=True, exist_ok=True)

    recent = paths.cron_results_dir / "recent.md"
    recent.write_text("recent")

    config = _make_config(cron_results_days=7)
    observer = CleanupObserver(config, paths)
    await observer._execute()

    assert recent.exists()


# -- Task cleanup via registry callback --


async def test_execute_uses_task_cleanup_fn(tmp_path: Path) -> None:
    """When set_task_cleanup is called, the observer uses the callback."""
    paths = _make_paths(tmp_path)
    config = _make_config(task_days=14)
    observer = CleanupObserver(config, paths)

    calls: list[int] = []

    def fake_cleanup_old(max_age_hours: int) -> int:
        calls.append(max_age_hours)
        return 3

    observer.set_task_cleanup(fake_cleanup_old)
    await observer._execute()

    assert calls == [14 * 24]  # task_days converted to hours


async def test_execute_falls_back_to_file_cleanup_without_registry(
    tmp_path: Path,
) -> None:
    """Without a task cleanup callback, old files in tasks/ are deleted by age."""
    paths = _make_paths(tmp_path)
    task_dir = paths.tasks_dir
    task_dir.mkdir(parents=True, exist_ok=True)

    old_task = task_dir / "abc123" / "TASKMEMORY.md"
    old_task.parent.mkdir()
    old_task.write_text("old task")
    old_mtime = time.time() - 20 * 86400
    os.utime(old_task, (old_mtime, old_mtime))

    recent_task = task_dir / "def456" / "TASKMEMORY.md"
    recent_task.parent.mkdir()
    recent_task.write_text("recent task")

    config = _make_config(task_days=14)
    observer = CleanupObserver(config, paths)
    await observer._execute()

    assert not old_task.exists()
    assert recent_task.exists()


# -- Config changes --


async def test_config_change_affects_next_run(tmp_path: Path) -> None:
    """Changing config values (e.g. cron_results_days) affects the next cleanup."""
    paths = _make_paths(tmp_path)
    paths.cron_results_dir.mkdir(parents=True, exist_ok=True)

    # File is 5 days old
    file = paths.cron_results_dir / "result.md"
    file.write_text("data")
    old_mtime = time.time() - 5 * 86400
    os.utime(file, (old_mtime, old_mtime))

    config = _make_config(cron_results_days=7)
    observer = CleanupObserver(config, paths)

    # With 7-day threshold, file should survive
    await observer._execute()
    assert file.exists()

    # Simulate hot-reload: change config to 3 days
    config.cleanup.cron_results_days = 3

    # Now the same file should be cleaned
    # Re-create the file since execute runs in thread and state is clean
    file.write_text("data")
    os.utime(file, (old_mtime, old_mtime))
    await observer._execute()
    assert not file.exists()
