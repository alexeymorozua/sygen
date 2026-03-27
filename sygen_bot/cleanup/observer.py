"""Cleanup observer: daily removal of old files from workspace directories."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sygen_bot.config import resolve_user_timezone
from sygen_bot.infra.base_observer import BaseObserver

if TYPE_CHECKING:
    from collections.abc import Callable

    from sygen_bot.config import AgentConfig, CleanupConfig
    from sygen_bot.workspace.paths import SygenPaths

logger = logging.getLogger(__name__)

_CHECK_INTERVAL = 3600  # Re-check every hour whether it's time to run.


def _delete_old_files(directory: Path, max_age_days: int) -> int:
    """Delete files older than *max_age_days* from *directory*.

    Walks the directory tree recursively, removes old files, then prunes
    empty subdirectories so date-based folders (``YYYY-MM-DD/``) don't
    accumulate indefinitely.
    """
    if not directory.is_dir():
        return 0

    cutoff = time.time() - max_age_days * 86400
    deleted = 0
    for entry in directory.rglob("*"):
        if not entry.is_file():
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
                deleted += 1
        except OSError:
            logger.warning("Failed to delete %s", entry)

    # Prune empty subdirectories (bottom-up so nested empties are removed)
    for sub in sorted(directory.rglob("*"), reverse=True):
        if sub.is_dir():
            with contextlib.suppress(OSError):
                sub.rmdir()  # only succeeds if empty
    return deleted


class CleanupObserver(BaseObserver):
    """Runs daily file cleanup for media files, output, api files, tasks, and cron results.

    Follows the same lifecycle pattern as HeartbeatObserver:
    ``start()`` / ``stop()`` with an asyncio background task.
    """

    def __init__(self, config: AgentConfig, paths: SygenPaths) -> None:
        super().__init__()
        self._config = config
        self._paths = paths
        self._last_run_date: str = ""
        self._task_cleanup_fn: Callable[[int], int] | None = None

    def set_task_cleanup(self, fn: Callable[[int], int]) -> None:
        """Set a callback for cleaning old tasks (e.g. ``TaskRegistry.cleanup_old``).

        The callback receives ``max_age_hours`` and returns the number of
        tasks removed.  When set, the observer delegates task cleanup to
        this function instead of doing raw file-age deletion on the tasks
        directory (which would bypass the registry).
        """
        self._task_cleanup_fn = fn

    @property
    def _cfg(self) -> CleanupConfig:
        return self._config.cleanup

    async def start(self) -> None:
        """Start the cleanup background loop."""
        if not self._cfg.enabled:
            logger.info("File cleanup disabled in config")
            return
        await super().start()
        logger.info(
            "File cleanup started (media: %dd, output: %dd, api: %dd, "
            "tasks: %dd, cron_results: %dd, hour: %d:00)",
            self._cfg.media_files_days,
            self._cfg.output_to_user_days,
            self._cfg.api_files_days,
            self._cfg.task_days,
            self._cfg.cron_results_days,
            self._cfg.check_hour,
        )

    async def stop(self) -> None:
        """Stop the cleanup background loop."""
        await super().stop()
        logger.info("File cleanup stopped")

    async def _run(self) -> None:
        """Sleep -> check hour -> run if due -> repeat."""
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
                    logger.exception("Cleanup tick failed (continuing)")
        except asyncio.CancelledError:
            logger.debug("Cleanup loop cancelled")

    async def _maybe_run(self) -> None:
        """Run cleanup if the current hour matches and we haven't run today."""
        tz = resolve_user_timezone(self._config.user_timezone)
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")

        if now.hour != self._cfg.check_hour:
            return
        if self._last_run_date == today:
            return

        await self._execute()
        # Set AFTER successful execution so a transient error doesn't
        # permanently suppress cleanup for the rest of the day.
        self._last_run_date = today

    async def _execute(self) -> None:
        """Perform the actual cleanup in a thread to avoid blocking the loop."""
        cfg = self._cfg
        targets = [
            (self._paths.telegram_files_dir, cfg.media_files_days),
            (self._paths.output_to_user_dir, cfg.output_to_user_days),
            (self._paths.api_files_dir, cfg.api_files_days),
            (self._paths.matrix_files_dir, cfg.media_files_days),
            (self._paths.cron_results_dir, cfg.cron_results_days),
        ]
        results = await asyncio.to_thread(_run_cleanup, targets)

        # Task cleanup: prefer registry-aware callback, fall back to file-age.
        task_cleanup_fn = self._task_cleanup_fn
        if task_cleanup_fn is not None:
            tasks_removed = await asyncio.to_thread(
                task_cleanup_fn, cfg.task_days * 24
            )
        else:
            tasks_removed = await asyncio.to_thread(
                _delete_old_files, self._paths.tasks_dir, cfg.task_days
            )

        if any(results) or tasks_removed:
            logger.info(
                "Cleanup complete: telegram=%d, output=%d, api=%d, "
                "matrix=%d, cron_results=%d, tasks=%d",
                results[0],
                results[1],
                results[2],
                results[3],
                results[4],
                tasks_removed,
            )
        else:
            logger.debug("Cleanup: nothing to delete")


def _run_cleanup(targets: list[tuple[Path, int]]) -> list[int]:
    """Synchronous cleanup runner (called via ``asyncio.to_thread``)."""
    return [_delete_old_files(d, days) for d, days in targets]
