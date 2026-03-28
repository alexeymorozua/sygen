"""Memory observer: periodic mechanical maintenance of the memory system.

Handles tasks that do NOT require LLM intelligence:
- Deduplicate identical lines within memory modules
- Enforce per-module line limits
- Remove empty or broken module files
- Clean orphaned session JSONL files not referenced in sessions.json
- Remove completed one-shot crons from cron_jobs.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sygen_bot.config import resolve_user_timezone
from sygen_bot.infra.base_observer import BaseObserver

if TYPE_CHECKING:
    from sygen_bot.config import AgentConfig, MemoryConfig
    from sygen_bot.workspace.paths import SygenPaths

logger = logging.getLogger(__name__)

_CHECK_INTERVAL = 3600  # Re-check every hour whether it's time to run.


class MemoryObserver(BaseObserver):
    """Runs periodic mechanical memory maintenance.

    Follows the same lifecycle as CleanupObserver:
    ``start()`` / ``stop()`` with an asyncio background task.
    """

    def __init__(self, config: AgentConfig, paths: SygenPaths) -> None:
        super().__init__()
        self._config = config
        self._paths = paths
        self._last_run_date: str = ""

    @property
    def _cfg(self) -> MemoryConfig:
        return self._config.memory

    async def start(self) -> None:
        if not self._cfg.enabled:
            logger.info("Memory observer disabled in config")
            return
        await super().start()
        logger.info(
            "Memory observer started (module_line_limit=%d, "
            "session_max_age_days=%d, check_hour=%d:00)",
            self._cfg.module_line_limit,
            self._cfg.session_max_age_days,
            self._cfg.check_hour,
        )

    async def stop(self) -> None:
        await super().stop()
        logger.info("Memory observer stopped")

    async def _run(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(_CHECK_INTERVAL)
                if not self._running or not self._cfg.enabled:
                    continue
                try:
                    await self._maybe_run()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Memory observer tick failed (continuing)")
        except asyncio.CancelledError:
            logger.debug("Memory observer loop cancelled")

    async def _maybe_run(self) -> None:
        tz = resolve_user_timezone(self._config.user_timezone)
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")

        if now.hour != self._cfg.check_hour:
            return
        if self._last_run_date == today:
            return

        await self._execute()
        self._last_run_date = today

    async def _execute(self) -> None:
        results = await asyncio.to_thread(self._run_maintenance)
        if any(v > 0 for v in results.values()):
            logger.info("Memory maintenance: %s", results)
        else:
            logger.debug("Memory maintenance: nothing to do")

    def _run_maintenance(self) -> dict[str, int]:
        """Synchronous maintenance runner (called via ``asyncio.to_thread``)."""
        results: dict[str, int] = {}
        results["dedup_lines"] = _dedup_modules(
            self._paths.memory_system_dir / "modules"
        )
        results["trimmed_modules"] = _enforce_line_limits(
            self._paths.memory_system_dir / "modules",
            self._cfg.module_line_limit,
        )
        results["empty_removed"] = _remove_empty_modules(
            self._paths.memory_system_dir / "modules"
        )
        results["orphan_sessions"] = _clean_orphan_sessions(
            self._paths.sessions_path,
            self._paths.sygen_home,
            self._cfg.session_max_age_days,
        )
        results["oneshot_crons"] = _clean_oneshot_crons(
            self._paths.cron_jobs_path,
        )
        return results


# ---------------------------------------------------------------------------
# Mechanical maintenance functions
# ---------------------------------------------------------------------------


def _dedup_modules(modules_dir: Path) -> int:
    """Remove exact duplicate lines within each memory module file.

    Preserves order: keeps the first occurrence of each line.
    Ignores blank lines and section headers (lines starting with #).
    """
    if not modules_dir.is_dir():
        return 0

    total_removed = 0
    for md_file in modules_dir.glob("*.md"):
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            continue

        seen: set[str] = set()
        deduped: list[str] = []
        removed = 0
        for line in lines:
            stripped = line.strip()
            # Always keep blank lines and headers
            if not stripped or stripped.startswith("#"):
                deduped.append(line)
                continue
            if stripped in seen:
                removed += 1
                continue
            seen.add(stripped)
            deduped.append(line)

        if removed > 0:
            md_file.write_text("".join(deduped), encoding="utf-8")
            total_removed += removed
            logger.debug("Dedup %s: removed %d duplicate lines", md_file.name, removed)

    return total_removed


def _enforce_line_limits(modules_dir: Path, limit: int) -> int:
    """Trim modules that exceed *limit* lines by removing oldest entries.

    Oldest = lines closest to the top of the file, after any leading
    header/metadata section (lines starting with ``#`` or ``---``).
    """
    if not modules_dir.is_dir() or limit <= 0:
        return 0

    trimmed = 0
    for md_file in modules_dir.glob("*.md"):
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            continue

        if len(lines) <= limit:
            continue

        # Find where the header ends (consecutive # or --- lines at the top)
        header_end = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("#") or s == "---" or not s:
                header_end = i + 1
            else:
                break

        # Keep header + last (limit - header_end) content lines
        content_budget = max(limit - header_end, limit // 2)
        content_lines = lines[header_end:]
        if len(content_lines) > content_budget:
            kept = lines[:header_end] + content_lines[-content_budget:]
            md_file.write_text("".join(kept), encoding="utf-8")
            trimmed += 1
            logger.debug(
                "Trimmed %s: %d -> %d lines",
                md_file.name,
                len(lines),
                len(kept),
            )

    return trimmed


def _remove_empty_modules(modules_dir: Path) -> int:
    """Delete module files that are empty or contain only whitespace."""
    if not modules_dir.is_dir():
        return 0

    removed = 0
    for md_file in modules_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not content:
            md_file.unlink()
            removed += 1
            logger.debug("Removed empty module: %s", md_file.name)

    return removed


def _clean_orphan_sessions(
    sessions_path: Path,
    sygen_home: Path,
    max_age_days: int,
) -> int:
    """Remove session JSONL files not referenced in sessions.json and older than max_age_days."""
    if not sessions_path.is_file():
        return 0

    # Find all session directories that may contain .jsonl files
    sessions_dir = sygen_home / "sessions"
    if not sessions_dir.is_dir():
        return 0

    # Load referenced session IDs
    try:
        data = json.loads(sessions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    referenced: set[str] = set()
    if isinstance(data, dict):
        for _key, session in data.items():
            if isinstance(session, dict):
                sid = session.get("session_id") or session.get("id", "")
                if sid:
                    referenced.add(str(sid))

    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for f in sessions_dir.rglob("*.jsonl"):
        stem = f.stem
        if stem in referenced:
            continue
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass

    if removed:
        logger.debug("Cleaned %d orphaned session files", removed)
    return removed


def _clean_oneshot_crons(cron_jobs_path: Path) -> int:
    """Remove one-shot crons that have already executed.

    A one-shot cron has a ``"once": true`` field and a non-null ``last_run_at``.
    """
    if not cron_jobs_path.is_file():
        return 0

    try:
        raw = json.loads(cron_jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    # Support both list format and {"jobs": [...]} format
    if isinstance(raw, dict) and "jobs" in raw:
        jobs = raw["jobs"]
        wrapper = raw
    elif isinstance(raw, list):
        jobs = raw
        wrapper = None
    else:
        return 0

    original_count = len(jobs)
    kept = [
        job
        for job in jobs
        if not (
            isinstance(job, dict)
            and job.get("once") is True
            and job.get("last_run_at") is not None
        )
    ]

    removed = original_count - len(kept)
    if removed > 0:
        if wrapper is not None:
            wrapper["jobs"] = kept
            output = wrapper
        else:
            output = kept
        cron_jobs_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.debug("Removed %d completed one-shot crons", removed)

    return removed
