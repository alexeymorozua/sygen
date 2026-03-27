"""Tests for the observability trace recorder and cleanup."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from sygen_bot.observability.recorder import record_trace, read_traces, Trace
from sygen_bot.observability.cleanup import run_cleanup


@pytest.fixture()
def logs_dir(tmp_path: Path) -> Path:
    return tmp_path / "logs"


def _record(
    logs_dir: Path,
    *,
    name: str = "test-job",
    trace_type: str = "cron",
    status: str = "ok",
    minutes_ago: int = 0,
) -> None:
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    record_trace(
        logs_dir,
        trace_type=trace_type,
        name=name,
        started=now,
        finished=now + timedelta(seconds=5),
        duration_sec=5.0,
        status=status,
        provider="claude",
        model="opus",
        summary="done",
    )


class TestRecordTrace:
    def test_creates_db_and_inserts(self, logs_dir: Path) -> None:
        _record(logs_dir)
        assert (logs_dir / "traces.db").is_file()
        traces = read_traces(logs_dir)
        assert len(traces) == 1
        assert traces[0].name == "test-job"
        assert traces[0].status == "ok"

    def test_summary_truncated_to_200(self, logs_dir: Path) -> None:
        now = datetime.now(timezone.utc)
        record_trace(
            logs_dir,
            trace_type="task",
            name="long",
            started=now,
            finished=now + timedelta(seconds=1),
            duration_sec=1.0,
            status="ok",
            provider="claude",
            model="opus",
            summary="x" * 500,
        )
        traces = read_traces(logs_dir)
        assert len(traces[0].summary) == 200  # type: ignore[arg-type]

    def test_status_normalization(self, logs_dir: Path) -> None:
        now = datetime.now(timezone.utc)
        for raw, expected in [
            ("success", "ok"),
            ("error:cli", "error"),
            ("error:timeout", "timeout"),
            ("aborted", "aborted"),
        ]:
            record_trace(
                logs_dir,
                trace_type="cron",
                name=f"job-{raw}",
                started=now,
                finished=now + timedelta(seconds=1),
                duration_sec=1.0,
                status=raw,
                provider="claude",
                model="opus",
            )
        traces = read_traces(logs_dir, limit=100)
        statuses = {t.name: t.status for t in traces}
        assert statuses["job-success"] == "ok"
        assert statuses["job-error:cli"] == "error"
        assert statuses["job-error:timeout"] == "timeout"
        assert statuses["job-aborted"] == "aborted"

    def test_error_cleared_on_ok_status(self, logs_dir: Path) -> None:
        now = datetime.now(timezone.utc)
        record_trace(
            logs_dir,
            trace_type="cron",
            name="clean",
            started=now,
            finished=now + timedelta(seconds=1),
            duration_sec=1.0,
            status="ok",
            provider="claude",
            model="opus",
            error="should be ignored",
        )
        traces = read_traces(logs_dir)
        assert traces[0].error is None


class TestReadTraces:
    def test_filter_by_type(self, logs_dir: Path) -> None:
        _record(logs_dir, name="cron-job", trace_type="cron")
        _record(logs_dir, name="bg-task", trace_type="task")
        crons = read_traces(logs_dir, trace_type="cron")
        assert all(t.type == "cron" for t in crons)
        assert len(crons) == 1

    def test_filter_by_name(self, logs_dir: Path) -> None:
        _record(logs_dir, name="alpha")
        _record(logs_dir, name="beta")
        results = read_traces(logs_dir, name="alpha")
        assert len(results) == 1
        assert results[0].name == "alpha"

    def test_errors_only(self, logs_dir: Path) -> None:
        _record(logs_dir, name="good", status="ok")
        _record(logs_dir, name="bad", status="error:cli")
        errors = read_traces(logs_dir, errors_only=True)
        assert len(errors) == 1
        assert errors[0].name == "bad"

    def test_limit(self, logs_dir: Path) -> None:
        for i in range(20):
            _record(logs_dir, name=f"job-{i}", minutes_ago=i)
        traces = read_traces(logs_dir, limit=5)
        assert len(traces) == 5

    def test_ordered_by_started_desc(self, logs_dir: Path) -> None:
        _record(logs_dir, name="old", minutes_ago=10)
        _record(logs_dir, name="new", minutes_ago=0)
        traces = read_traces(logs_dir, limit=10)
        assert traces[0].name == "new"
        assert traces[1].name == "old"

    def test_no_db_returns_empty(self, logs_dir: Path) -> None:
        assert read_traces(logs_dir) == []


class TestCleanup:
    def test_age_based_cleanup(self, logs_dir: Path) -> None:
        _record(logs_dir, name="old", minutes_ago=60 * 24 * 40)  # 40 days ago
        _record(logs_dir, name="recent", minutes_ago=0)
        # Force cleanup
        db_path = logs_dir / "traces.db"
        conn = sqlite3.connect(str(db_path), timeout=5)
        run_cleanup(conn, retention_days=30, max_rows=1000)
        conn.close()
        traces = read_traces(logs_dir)
        assert len(traces) == 1
        assert traces[0].name == "recent"

    def test_count_based_cleanup(self, logs_dir: Path) -> None:
        for i in range(15):
            _record(logs_dir, name=f"job-{i}", minutes_ago=i)
        db_path = logs_dir / "traces.db"
        conn = sqlite3.connect(str(db_path), timeout=5)
        run_cleanup(conn, retention_days=365, max_rows=10)
        conn.close()
        traces = read_traces(logs_dir, limit=100)
        assert len(traces) == 10
