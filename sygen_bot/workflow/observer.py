"""Filesystem observer for workflow YAML definitions.

Polls the ``workflows/`` directory for changes (new, modified, deleted
YAML files) and reloads definitions in the WorkflowEngine's registry.
Follows the same polling pattern as :class:`CronObserver`.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.workflow.engine import WorkflowEngine
    from sygen_bot.workspace.paths import SygenPaths

logger = logging.getLogger(__name__)

_POLL_INTERVAL: float = 5.0  # seconds


class WorkflowObserver:
    """Watch the ``workflows/`` directory and reload definitions on change.

    Uses a simple mtime-based polling approach (like CronObserver's
    FileWatcher) to detect changes in YAML files.
    """

    def __init__(self, engine: WorkflowEngine, paths: SygenPaths) -> None:
        self._engine = engine
        self._workflows_dir: Path = paths.workflows_dir
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._known_mtimes: dict[str, float] = {}

    @property
    def running(self) -> bool:
        return self._running

    def set_notify_callback(self, callback) -> None:
        """Delegate notify callback setup to the underlying engine."""
        self._engine.set_notify_callback(callback)

    async def start(self) -> None:
        """Start polling the workflows directory for changes."""
        if self._running:
            return
        self._running = True
        self._workflows_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_mtimes()
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(
            "WorkflowObserver started (watching %s, %d definitions)",
            self._workflows_dir,
            len(self._known_mtimes),
        )

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        if self._poll_task is not None and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("WorkflowObserver stopped")

    # ── Internal ─────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Poll for filesystem changes every ``_POLL_INTERVAL`` seconds."""
        while self._running:
            try:
                await asyncio.sleep(_POLL_INTERVAL)
            except asyncio.CancelledError:
                return
            try:
                if self._has_changes():
                    await self._reload_definitions()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("WorkflowObserver poll error")

    def _snapshot_mtimes(self) -> None:
        """Record current mtime for every YAML file in the directory."""
        self._known_mtimes.clear()
        if not self._workflows_dir.is_dir():
            return
        for path in self._workflows_dir.iterdir():
            if path.suffix in (".yaml", ".yml"):
                try:
                    self._known_mtimes[str(path)] = path.stat().st_mtime
                except OSError:
                    pass

    def _has_changes(self) -> bool:
        """Return True if any YAML file was added, removed, or modified."""
        if not self._workflows_dir.is_dir():
            return bool(self._known_mtimes)

        current: dict[str, float] = {}
        for path in self._workflows_dir.iterdir():
            if path.suffix in (".yaml", ".yml"):
                try:
                    current[str(path)] = path.stat().st_mtime
                except OSError:
                    pass

        if current != self._known_mtimes:
            return True
        return False

    async def _reload_definitions(self) -> None:
        """Reload all workflow definitions from YAML files."""
        logger.info("Workflow definitions changed, reloading")
        try:
            await asyncio.to_thread(
                self._engine._registry.load_definitions,
            )
            self._snapshot_mtimes()
            count = len(self._engine._registry.list_definitions())
            logger.info("Reloaded %d workflow definitions", count)
        except Exception:
            logger.exception("Failed to reload workflow definitions")
