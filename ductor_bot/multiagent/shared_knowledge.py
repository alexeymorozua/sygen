"""SharedKnowledgeSync: watches SHAREDMEMORY.md and injects into all agents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ductor_bot.infra.file_watcher import FileWatcher

if TYPE_CHECKING:
    from ductor_bot.multiagent.supervisor import AgentSupervisor

logger = logging.getLogger(__name__)

_START_MARKER = "<!-- SHARED:START -->"
_END_MARKER = "<!-- SHARED:END -->"


class SharedKnowledgeSync:
    """Watches ``SHAREDMEMORY.md`` and syncs its content into every agent's MAINMEMORY.md.

    The shared content is wrapped in ``<!-- SHARED:START -->`` / ``<!-- SHARED:END -->``
    markers.  Existing blocks are replaced in-place; if no markers exist yet the
    block is appended.  Compatible with the legacy bash sync script.
    """

    def __init__(self, shared_path: Path, supervisor: AgentSupervisor) -> None:
        self._path = shared_path
        self._supervisor = supervisor
        self._watcher = FileWatcher(self._path, self._on_changed)

    @property
    def path(self) -> Path:
        return self._path

    async def start(self) -> None:
        """Start watching and perform an initial sync."""
        if self._path.is_file():
            self._sync_all()
        await self._watcher.start()
        logger.info("SharedKnowledgeSync watching %s", self._path)

    async def stop(self) -> None:
        await self._watcher.stop()

    async def _on_changed(self) -> None:
        """FileWatcher callback — SHAREDMEMORY.md was modified."""
        logger.info("SHAREDMEMORY.md changed, syncing to all agents")
        self._sync_all()

    def sync_agent(self, mainmemory_path: Path) -> None:
        """Inject shared knowledge into a single agent's MAINMEMORY.md."""
        if not self._path.is_file():
            return
        shared_content = self._path.read_text(encoding="utf-8").strip()
        if not shared_content:
            return
        inject_block = f"{_START_MARKER}\n{shared_content}\n{_END_MARKER}"

        if not mainmemory_path.is_file():
            logger.debug("Skipping %s (file does not exist)", mainmemory_path)
            return

        current = mainmemory_path.read_text(encoding="utf-8")

        if _START_MARKER in current:
            # Replace existing block
            before = current.split(_START_MARKER, 1)[0]
            after_parts = current.split(_END_MARKER, 1)
            after = after_parts[1] if len(after_parts) > 1 else ""
            new_content = f"{before}{inject_block}{after}"
        else:
            # Append
            new_content = f"{current.rstrip()}\n\n{inject_block}\n"

        if new_content != current:
            mainmemory_path.write_text(new_content, encoding="utf-8")
            logger.info("Synced shared knowledge to %s", mainmemory_path)

    def _sync_all(self) -> None:
        """Inject into all registered agents' MAINMEMORY.md files."""
        for name, stack in self._supervisor.stacks.items():
            try:
                self.sync_agent(stack.paths.mainmemory_path)
            except Exception:
                logger.exception("Failed to sync shared knowledge to agent '%s'", name)
