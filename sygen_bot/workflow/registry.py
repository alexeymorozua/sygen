"""Workflow definition loading and run persistence."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from sygen_bot.infra.json_store import atomic_json_save, load_json
from sygen_bot.workflow.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
)

logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """Load workflow definitions from YAML and manage run state on disk."""

    def __init__(self, definitions_dir: Path, runs_path: Path) -> None:
        self._definitions_dir = definitions_dir
        self._runs_path = runs_path
        self._definitions: dict[str, WorkflowDefinition] = {}
        self._runs: dict[str, WorkflowRun] = {}
        self._load_definitions()
        self._load_runs()

    # ── Definitions ──────────────────────────────────────────────────

    def _load_definitions(self) -> None:
        """Scan *definitions_dir* for ``*.yaml`` / ``*.yml`` files."""
        self._definitions.clear()
        if not self._definitions_dir.is_dir():
            logger.warning(
                "Workflow definitions dir does not exist: %s",
                self._definitions_dir,
            )
            return
        for path in sorted(self._definitions_dir.iterdir()):
            if path.suffix not in (".yaml", ".yml"):
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                defn = WorkflowDefinition.model_validate(raw)
                self._definitions[defn.id] = defn
            except Exception:
                logger.exception("Failed to load workflow definition: %s", path)

    def load_definitions(self) -> dict[str, WorkflowDefinition]:
        """Reload and return all definitions."""
        self._load_definitions()
        return dict(self._definitions)

    def get_definition(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._definitions.get(workflow_id)

    def list_definitions(self) -> list[WorkflowDefinition]:
        return list(self._definitions.values())

    # ── Run persistence ──────────────────────────────────────────────

    def _load_runs(self) -> None:
        """Load runs from disk."""
        self._runs.clear()
        raw = load_json(self._runs_path)
        if raw is None:
            return
        runs_list = raw.get("runs", [])
        if not isinstance(runs_list, list):
            return
        for entry in runs_list:
            try:
                run = WorkflowRun.model_validate(entry)
                self._runs[run.run_id] = run
            except Exception:
                logger.warning("Skipping corrupt run entry")

    def _save_runs(self) -> None:
        """Persist all runs atomically."""
        data = {
            "runs": [r.model_dump(mode="json") for r in self._runs.values()]
        }
        atomic_json_save(self._runs_path, data)

    def create_run(
        self,
        workflow_id: str,
        chat_id: int,
        topic_id: int | None = None,
        transport: str = "tg",
        parent_agent: str = "main",
        variable_overrides: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Create a new workflow run and persist it."""
        defn = self._definitions.get(workflow_id)
        variables: dict[str, Any] = {}
        if defn is not None:
            variables.update(defn.variables)
        if variable_overrides:
            variables.update(variable_overrides)

        run = WorkflowRun(
            run_id=uuid.uuid4().hex,
            workflow_id=workflow_id,
            chat_id=chat_id,
            topic_id=topic_id,
            transport=transport,
            parent_agent=parent_agent,
            variables=variables,
            created_at=time.time(),
        )
        self._runs[run.run_id] = run
        self._save_runs()
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self._runs.get(run_id)

    def update_run(self, run: WorkflowRun) -> None:
        """Update an existing run in memory and on disk."""
        self._runs[run.run_id] = run
        self._save_runs()

    def list_runs(
        self, status_filter: WorkflowRunStatus | None = None
    ) -> list[WorkflowRun]:
        """Return runs, optionally filtered by status."""
        if status_filter is None:
            return list(self._runs.values())
        return [r for r in self._runs.values() if r.status == status_filter]

    def get_waiting_run(
        self, chat_id: int, topic_id: int | None = None
    ) -> WorkflowRun | None:
        """Find a run in WAITING status for the given chat/topic.

        Used to resume a ``wait_for_reply`` step when the user responds.
        """
        for run in self._runs.values():
            if run.status != WorkflowRunStatus.WAITING:
                continue
            if run.chat_id != chat_id:
                continue
            if run.topic_id != topic_id:
                continue
            return run
        return None
