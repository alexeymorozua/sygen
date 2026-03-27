"""Trace file rotation: age-based and count-based cleanup."""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def run_cleanup(
    traces_dir: Path,
    *,
    retention_days: int = 30,
    max_files: int = 1000,
) -> None:
    if not traces_dir.is_dir():
        return

    files = sorted(traces_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    cutoff = time.time() - (retention_days * 86400)

    removed = 0
    remaining: list[Path] = []
    for f in files:
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
            else:
                remaining.append(f)
        except OSError:
            remaining.append(f)

    if len(remaining) > max_files:
        excess = remaining[: len(remaining) - max_files]
        for f in excess:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    if removed:
        logger.info("Trace cleanup: removed %d files", removed)
