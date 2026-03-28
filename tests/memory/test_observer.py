"""Tests for the MemoryObserver mechanical maintenance functions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sygen_bot.memory.observer import (
    MemoryObserver,
    _clean_oneshot_crons,
    _clean_orphan_sessions,
    _dedup_modules,
    _enforce_line_limits,
    _remove_empty_modules,
)


@pytest.fixture
def modules_dir(tmp_path: Path) -> Path:
    d = tmp_path / "modules"
    d.mkdir()
    return d


# -- Dedup tests --


def test_dedup_removes_duplicate_lines(modules_dir: Path) -> None:
    f = modules_dir / "user.md"
    f.write_text("# User\n\nFact A\nFact B\nFact A\nFact C\nFact B\n")
    removed = _dedup_modules(modules_dir)
    assert removed == 2
    lines = f.read_text().splitlines()
    assert lines == ["# User", "", "Fact A", "Fact B", "Fact C"]


def test_dedup_keeps_headers_and_blanks(modules_dir: Path) -> None:
    f = modules_dir / "decisions.md"
    f.write_text("# Decisions\n\n# Section\n\n# Section\nLine\n")
    removed = _dedup_modules(modules_dir)
    # Headers and blanks are always kept, even if duplicated
    assert removed == 0


def test_dedup_no_changes_on_unique(modules_dir: Path) -> None:
    f = modules_dir / "tools.md"
    original = "# Tools\n\nTool A\nTool B\nTool C\n"
    f.write_text(original)
    removed = _dedup_modules(modules_dir)
    assert removed == 0
    assert f.read_text() == original


def test_dedup_nonexistent_dir(tmp_path: Path) -> None:
    assert _dedup_modules(tmp_path / "nope") == 0


# -- Line limit tests --


def test_enforce_limits_trims_long_modules(modules_dir: Path) -> None:
    f = modules_dir / "big.md"
    lines = ["# Header\n", "\n"] + [f"Line {i}\n" for i in range(100)]
    f.write_text("".join(lines))
    trimmed = _enforce_line_limits(modules_dir, 80)
    assert trimmed == 1
    result = f.read_text().splitlines()
    assert len(result) <= 80
    # Header should be preserved
    assert result[0] == "# Header"


def test_enforce_limits_keeps_short_modules(modules_dir: Path) -> None:
    f = modules_dir / "small.md"
    f.write_text("# Small\n\nOne line\n")
    assert _enforce_line_limits(modules_dir, 80) == 0


def test_enforce_limits_zero_limit(modules_dir: Path) -> None:
    f = modules_dir / "any.md"
    f.write_text("# Any\n\nContent\n")
    assert _enforce_line_limits(modules_dir, 0) == 0


# -- Empty module tests --


def test_remove_empty_modules(modules_dir: Path) -> None:
    (modules_dir / "empty.md").write_text("")
    (modules_dir / "whitespace.md").write_text("  \n\n  \n")
    (modules_dir / "good.md").write_text("# Good\nContent\n")
    removed = _remove_empty_modules(modules_dir)
    assert removed == 2
    assert not (modules_dir / "empty.md").exists()
    assert not (modules_dir / "whitespace.md").exists()
    assert (modules_dir / "good.md").exists()


def test_remove_empty_nonexistent(tmp_path: Path) -> None:
    assert _remove_empty_modules(tmp_path / "nope") == 0


# -- Session cleanup tests --


def test_clean_orphan_sessions(tmp_path: Path) -> None:
    sessions_json = tmp_path / "sessions.json"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    # Referenced session
    sessions_json.write_text(json.dumps({
        "chat_123": {"session_id": "active-session", "last_active": "2026-01-01"}
    }))

    # Active session file (referenced)
    (sessions_dir / "active-session.jsonl").write_text("{}\n")

    # Orphan session file (old)
    orphan = sessions_dir / "orphan-old.jsonl"
    orphan.write_text("{}\n")
    import os
    # Set mtime to 60 days ago
    old_time = __import__("time").time() - 60 * 86400
    os.utime(orphan, (old_time, old_time))

    removed = _clean_orphan_sessions(sessions_json, tmp_path, max_age_days=30)
    assert removed == 1
    assert not orphan.exists()
    assert (sessions_dir / "active-session.jsonl").exists()


def test_clean_orphan_sessions_keeps_recent(tmp_path: Path) -> None:
    sessions_json = tmp_path / "sessions.json"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    sessions_json.write_text("{}")
    (sessions_dir / "recent.jsonl").write_text("{}\n")

    removed = _clean_orphan_sessions(sessions_json, tmp_path, max_age_days=30)
    assert removed == 0


def test_clean_orphan_sessions_no_dir(tmp_path: Path) -> None:
    sessions_json = tmp_path / "sessions.json"
    sessions_json.write_text("{}")
    assert _clean_orphan_sessions(sessions_json, tmp_path, max_age_days=30) == 0


# -- One-shot cron tests --


def test_clean_oneshot_crons_list_format(tmp_path: Path) -> None:
    cron_file = tmp_path / "cron_jobs.json"
    cron_file.write_text(json.dumps([
        {"id": "keep", "schedule": "0 10 * * *", "enabled": True},
        {"id": "done", "schedule": "0 10 * * *", "once": True, "last_run_at": "2026-01-01"},
        {"id": "pending", "schedule": "0 10 * * *", "once": True, "last_run_at": None},
    ]))
    removed = _clean_oneshot_crons(cron_file)
    assert removed == 1
    remaining = json.loads(cron_file.read_text())
    assert len(remaining) == 2
    assert {j["id"] for j in remaining} == {"keep", "pending"}


def test_clean_oneshot_crons_dict_format(tmp_path: Path) -> None:
    cron_file = tmp_path / "cron_jobs.json"
    cron_file.write_text(json.dumps({
        "jobs": [
            {"id": "keep", "schedule": "0 10 * * *"},
            {"id": "done", "once": True, "last_run_at": "2026-03-01"},
        ]
    }))
    removed = _clean_oneshot_crons(cron_file)
    assert removed == 1
    data = json.loads(cron_file.read_text())
    assert len(data["jobs"]) == 1


def test_clean_oneshot_crons_no_file(tmp_path: Path) -> None:
    assert _clean_oneshot_crons(tmp_path / "missing.json") == 0


# -- Observer lifecycle tests --


@pytest.mark.asyncio
async def test_observer_disabled() -> None:
    config = MagicMock()
    config.memory.enabled = False
    paths = MagicMock()

    obs = MemoryObserver(config, paths)
    await obs.start()
    assert not obs.running


@pytest.mark.asyncio
async def test_observer_start_stop() -> None:
    config = MagicMock()
    config.memory.enabled = True
    config.memory.module_line_limit = 80
    config.memory.session_max_age_days = 30
    config.memory.check_hour = 4
    paths = MagicMock()

    obs = MemoryObserver(config, paths)
    await obs.start()
    assert obs.running
    await obs.stop()
    assert not obs.running
