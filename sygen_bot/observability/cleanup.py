"""Trace rotation: age-based and count-based cleanup via SQL."""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def run_cleanup(
    conn: sqlite3.Connection,
    *,
    retention_days: int = 30,
    max_rows: int = 1000,
) -> None:
    deleted = 0

    cur = conn.execute(
        "DELETE FROM traces WHERE started < datetime('now', ?)",
        (f"-{retention_days} days",),
    )
    deleted += cur.rowcount

    count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    if count > max_rows:
        excess = count - max_rows
        cur = conn.execute(
            "DELETE FROM traces WHERE id IN "
            "(SELECT id FROM traces ORDER BY started ASC LIMIT ?)",
            (excess,),
        )
        deleted += cur.rowcount

    if deleted:
        conn.commit()
        logger.info("Trace cleanup: removed %d rows", deleted)
