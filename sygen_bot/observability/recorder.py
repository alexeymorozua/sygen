"""Trace recorder: writes and reads structured traces in SQLite."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sygen_bot.observability.cleanup import run_cleanup

logger = logging.getLogger(__name__)

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    started TEXT NOT NULL,
    finished TEXT NOT NULL,
    duration_sec REAL NOT NULL,
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    error TEXT,
    summary TEXT,
    agent_name TEXT NOT NULL DEFAULT '',
    job_id TEXT NOT NULL DEFAULT ''
)
"""

_CREATE_INDEX = """\
CREATE INDEX IF NOT EXISTS idx_traces_started ON traces (started DESC)
"""

_MIGRATE_COLUMNS = [
    ("agent_name", "TEXT NOT NULL DEFAULT ''"),
    ("job_id", "TEXT NOT NULL DEFAULT ''"),
]


@dataclass(frozen=True, slots=True)
class Trace:
    id: str
    type: str  # "cron" | "task" | "webhook"
    name: str
    started: str
    finished: str
    duration_sec: float
    status: str  # "ok" | "error" | "timeout" | "aborted"
    provider: str
    model: str
    error: str | None = None
    summary: str | None = None
    agent_name: str = ""
    job_id: str = ""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_INDEX)
    for col_name, col_def in _MIGRATE_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE traces ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass
    return conn


def _normalize_status(raw_status: str) -> str:
    if raw_status in ("ok", "success"):
        return "ok"
    if "timeout" in raw_status:
        return "timeout"
    if raw_status == "aborted":
        return "aborted"
    if raw_status.startswith("error") or raw_status.startswith("skipped"):
        return "error"
    return "ok"


def record_trace(
    logs_dir: Path,
    *,
    trace_type: str,
    name: str,
    started: datetime,
    finished: datetime,
    duration_sec: float,
    status: str,
    provider: str,
    model: str,
    error: str | None = None,
    summary: str | None = None,
    retention_days: int = 30,
    max_files: int = 1000,
    agent_name: str = "",
    job_id: str = "",
) -> None:
    normalized = _normalize_status(status)
    ts = started.strftime("%Y%m%d-%H%M%S")
    trace_id = f"{trace_type}-{name}-{ts}"

    db_path = logs_dir / "traces.db"
    try:
        conn = _connect(db_path)
    except sqlite3.Error:
        logger.exception("Failed to open traces database")
        return

    try:
        conn.execute(
            "INSERT OR REPLACE INTO traces "
            "(id, type, name, started, finished, duration_sec, status, provider, model, error, summary, agent_name, job_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                trace_type,
                name,
                started.isoformat(),
                finished.isoformat(),
                round(duration_sec, 1),
                normalized,
                provider or "",
                model or "",
                error if normalized != "ok" else None,
                summary[:200] if summary else None,
                agent_name or "",
                job_id or "",
            ),
        )
        conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to write trace %s", trace_id)
        conn.close()
        return

    try:
        run_cleanup(conn, retention_days=retention_days, max_rows=max_files)
    except Exception:
        logger.exception("Trace cleanup failed")
    finally:
        conn.close()


def read_traces(
    logs_dir: Path,
    *,
    trace_type: str | None = None,
    name: str | None = None,
    errors_only: bool = False,
    since: datetime | None = None,
    limit: int = 10,
) -> list[Trace]:
    db_path = logs_dir / "traces.db"
    if not db_path.is_file():
        return []

    try:
        conn = _connect(db_path)
    except sqlite3.Error:
        logger.exception("Failed to open traces database for reading")
        return []

    try:
        clauses: list[str] = []
        params: list[object] = []

        if trace_type:
            clauses.append("type = ?")
            params.append(trace_type)
        if name:
            clauses.append("name = ?")
            params.append(name)
        if errors_only:
            clauses.append("status != 'ok'")
        if since:
            clauses.append("started >= ?")
            params.append(since.isoformat())

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT id, type, name, started, finished, duration_sec, status, provider, model, error, summary, agent_name, job_id FROM traces{where} ORDER BY started DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [
            Trace(
                id=r[0], type=r[1], name=r[2], started=r[3], finished=r[4],
                duration_sec=r[5], status=r[6], provider=r[7], model=r[8],
                error=r[9], summary=r[10], agent_name=r[11], job_id=r[12],
            )
            for r in rows
        ]
    except sqlite3.Error:
        logger.exception("Failed to read traces")
        return []
    finally:
        conn.close()
