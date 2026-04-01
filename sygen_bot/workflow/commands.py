"""Slash-command handler for /workflow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sygen_bot.orchestrator.registry import OrchestratorResult

if TYPE_CHECKING:
    from sygen_bot.orchestrator.core import Orchestrator
    from sygen_bot.session.key import SessionKey

logger = logging.getLogger(__name__)


async def cmd_workflow(
    orch: Orchestrator, key: SessionKey, text: str,
) -> OrchestratorResult:
    """Handle ``/workflow [subcommand]``."""
    parts = text.strip().split(None, 1)
    args = parts[1].strip() if len(parts) > 1 else ""
    sub_parts = args.split(None, 1)
    sub = sub_parts[0].lower() if sub_parts else "list"
    sub_args = sub_parts[1] if len(sub_parts) > 1 else ""

    engine = getattr(orch, "_workflow_engine", None)
    if engine is None:
        return OrchestratorResult(text="Workflow engine is not enabled.")

    if sub in ("", "list"):
        return _list(engine)
    if sub == "runs":
        return _runs(engine)
    if sub == "run":
        return await _run(engine, key, sub_args)
    if sub == "status":
        return _status(engine, sub_args.strip())
    if sub == "cancel":
        return await _cancel(engine, sub_args.strip())

    return OrchestratorResult(
        text=(
            "**Usage:** `/workflow [subcommand]`\n\n"
            "Subcommands: `list`, `run <id>`, `status <run_id>`, "
            "`cancel <run_id>`, `runs`"
        ),
    )


# ── Subcommand handlers ─────────────────────────────────────────────


def _list(engine: object) -> OrchestratorResult:
    """List workflow definitions and active runs."""
    registry = engine._registry  # type: ignore[attr-defined]
    definitions = registry.list_definitions()
    if not definitions:
        return OrchestratorResult(text="No workflow definitions found.")

    lines: list[str] = ["**Workflow Definitions**\n"]
    for defn in definitions:
        trigger = ""
        if defn.trigger.cron:
            trigger = f" (cron: `{defn.trigger.cron}`)"
        elif defn.trigger.manual:
            trigger = " (manual)"
        lines.append(f"- `{defn.id}` — {defn.name}{trigger}")

    from sygen_bot.workflow.models import WorkflowRunStatus

    active = registry.list_runs(WorkflowRunStatus.RUNNING) + registry.list_runs(
        WorkflowRunStatus.WAITING
    )
    if active:
        lines.append("\n**Active Runs**\n")
        for run in active:
            lines.append(
                f"- `{run.run_id}` ({run.workflow_id}) — {run.status.value}"
                f" step=`{run.current_step_id}`"
            )

    return OrchestratorResult(text="\n".join(lines))


def _runs(engine: object) -> OrchestratorResult:
    """List all workflow runs."""
    registry = engine._registry  # type: ignore[attr-defined]
    runs = registry.list_runs()
    if not runs:
        return OrchestratorResult(text="No workflow runs.")

    lines: list[str] = ["**Workflow Runs**\n"]
    for run in runs:
        lines.append(
            f"- `{run.run_id}` ({run.workflow_id}) — **{run.status.value}**"
            f" step=`{run.current_step_id}`"
        )
    return OrchestratorResult(text="\n".join(lines))


async def _run(engine: object, key: object, args: str) -> OrchestratorResult:
    """Start a workflow run."""
    tokens = args.split()
    if not tokens:
        return OrchestratorResult(text="Usage: `/workflow run <workflow_id> [--var key=val ...]`")

    workflow_id = tokens[0]
    variables: dict[str, str] = {}
    i = 1
    while i < len(tokens):
        if tokens[i] == "--var" and i + 1 < len(tokens):
            kv = tokens[i + 1]
            if "=" in kv:
                k, v = kv.split("=", 1)
                variables[k] = v
            i += 2
        else:
            i += 1

    registry = engine._registry  # type: ignore[attr-defined]
    defn = registry.get_definition(workflow_id)
    if defn is None:
        return OrchestratorResult(text=f"Workflow `{workflow_id}` not found.")

    try:
        run_id = await engine.start_workflow(  # type: ignore[attr-defined]
            workflow_id,
            chat_id=key.chat_id,  # type: ignore[attr-defined]
            topic_id=key.topic_id,  # type: ignore[attr-defined]
            transport="tg",
            parent_agent="main",
            variable_overrides=variables or None,
        )
    except Exception as exc:
        logger.exception("Failed to start workflow %s", workflow_id)
        return OrchestratorResult(text=f"Failed to start workflow: {exc}")

    return OrchestratorResult(
        text=f"Workflow `{workflow_id}` started — run `{run_id}`",
    )


def _status(engine: object, run_id: str) -> OrchestratorResult:
    """Show detailed status of a workflow run."""
    if not run_id:
        return OrchestratorResult(text="Usage: `/workflow status <run_id>`")

    registry = engine._registry  # type: ignore[attr-defined]
    run = registry.get_run(run_id)
    if run is None:
        return OrchestratorResult(text=f"Run `{run_id}` not found.")

    lines: list[str] = [
        f"**Run** `{run.run_id}` — workflow `{run.workflow_id}`",
        f"**Status:** {run.status.value}",
        f"**Current step:** `{run.current_step_id or '-'}`",
    ]
    if run.error:
        lines.append(f"**Error:** {run.error}")
    if run.variables:
        var_str = ", ".join(f"`{k}`=`{v}`" for k, v in run.variables.items())
        lines.append(f"**Variables:** {var_str}")

    if run.step_runs:
        lines.append("\n**Steps:**")
        for sid, sr in run.step_runs.items():
            status_icon = {
                "completed": "done",
                "failed": "ERR",
                "running": "...",
                "waiting": "wait",
                "skipped": "skip",
                "pending": "-",
            }.get(sr.status.value, sr.status.value)
            out_preview = sr.output[:60].replace("\n", " ") if sr.output else ""
            lines.append(f"  `{sid}` [{status_icon}] {out_preview}")

    return OrchestratorResult(text="\n".join(lines))


async def _cancel(engine: object, run_id: str) -> OrchestratorResult:
    """Cancel a workflow run."""
    if not run_id:
        return OrchestratorResult(text="Usage: `/workflow cancel <run_id>`")

    try:
        cancelled = await engine.cancel_workflow(run_id)  # type: ignore[attr-defined]
    except Exception as exc:
        return OrchestratorResult(text=f"Cancel failed: {exc}")

    if cancelled:
        return OrchestratorResult(text=f"Run `{run_id}` cancelled.")
    return OrchestratorResult(text=f"Run `{run_id}` not found or already finished.")
