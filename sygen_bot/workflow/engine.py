"""Workflow execution engine.

Orchestrates step-by-step workflow execution with support for
pausing on user input, retries, fallbacks, and parallel steps.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from sygen_bot.workflow.models import (
    ErrorAction,
    StepDefinition,
    StepRun,
    StepStatus,
    StepType,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
)
from sygen_bot.workflow.variables import resolve_variables
from sygen_bot.workflow.executor import (
    WaitForReplySignal,
    WorkflowStepError,
    execute_ask_agent,
    execute_condition,
    execute_notify,
    execute_parallel,
    execute_wait_for_reply,
)

if TYPE_CHECKING:
    from sygen_bot.workflow.registry import WorkflowRegistry


class WorkflowEngine:
    """Execute workflow definitions step-by-step.

    Parameters
    ----------
    registry:
        WorkflowRegistry that holds definitions and persists runs.
    notify_callback:
        ``async fn(chat_id, topic_id, transport, message)`` used to send
        messages to the user.
    ask_agent_fn:
        Optional ``async fn(agent, prompt, timeout, **kw) -> str`` override
        for inter-agent communication. Falls back to ``execute_ask_agent``.
    """

    def __init__(
        self,
        registry: WorkflowRegistry,
        *,
        notify_callback: Callable[..., Awaitable[Any]],
        ask_agent_fn: Callable[..., Awaitable[str]] | None = None,
        max_parallel_runs: int = 5,
        default_step_timeout: float = 3600.0,
    ) -> None:
        self._registry = registry
        self._notify = notify_callback
        self._ask_agent = ask_agent_fn
        self._max_parallel_runs = max_parallel_runs
        self._default_step_timeout = default_step_timeout
        self._active_tasks: dict[str, asyncio.Task[None]] = {}
        self._logger = logging.getLogger(__name__)

    # ── Public API ──────────────────────────────────────────────────

    async def start_workflow(
        self,
        workflow_id: str,
        chat_id: int,
        topic_id: int | None,
        transport: str,
        parent_agent: str,
        variable_overrides: dict[str, Any] | None = None,
    ) -> str:
        """Start a new workflow run and return its run_id."""
        if len(self._active_tasks) >= self._max_parallel_runs:
            raise ValueError("Too many parallel workflow runs")

        definition = self._registry.get_definition(workflow_id)
        if not definition:
            raise ValueError(f"Workflow {workflow_id!r} not found")

        run = self._registry.create_run(
            workflow_id, chat_id, topic_id, transport, parent_agent,
            variable_overrides,
        )
        run.current_step_id = definition.steps[0].id
        run.status = WorkflowRunStatus.RUNNING
        self._registry.update_run(run)

        task = asyncio.create_task(self._execute_run(run.run_id))
        self._active_tasks[run.run_id] = task
        return run.run_id

    async def resume_workflow(self, run_id: str, user_reply: str) -> None:
        """Resume a workflow that is waiting for a user reply."""
        run = self._registry.get_run(run_id)
        if not run or run.status != WorkflowRunStatus.WAITING:
            return

        # Complete the waiting step with the user's reply
        step_run = run.step_runs.get(run.wait_step_id)
        if step_run:
            step_run.output = user_reply
            step_run.status = StepStatus.COMPLETED
            step_run.completed_at = time.time()

        # Resolve next step and continue
        definition = self._registry.get_definition(run.workflow_id)
        if not definition:
            return

        current_step = next(
            (s for s in definition.steps if s.id == run.wait_step_id), None
        )
        next_step_id = self._resolve_next_step(current_step, definition) if current_step else None

        if next_step_id:
            run.current_step_id = next_step_id
            run.status = WorkflowRunStatus.RUNNING
            run.wait_step_id = ""
            self._registry.update_run(run)
            task = asyncio.create_task(self._execute_run(run.run_id))
            self._active_tasks[run.run_id] = task
        else:
            run.status = WorkflowRunStatus.COMPLETED
            run.completed_at = time.time()
            self._registry.update_run(run)

    async def cancel_workflow(self, run_id: str) -> bool:
        """Cancel a running or waiting workflow."""
        task = self._active_tasks.pop(run_id, None)
        if task:
            task.cancel()
        run = self._registry.get_run(run_id)
        if not run:
            return False
        run.status = WorkflowRunStatus.CANCELLED
        run.completed_at = time.time()
        self._registry.update_run(run)
        return True

    def set_notify_callback(self, callback: Callable[..., Awaitable[Any]]) -> None:
        """Replace the notification callback (used during bus wiring)."""
        self._notify = callback

    async def shutdown(self) -> None:
        """Cancel all active workflow tasks. Called on application shutdown."""
        count = len(self._active_tasks)
        for run_id, task in list(self._active_tasks.items()):
            task.cancel()
        # Wait for all cancelled tasks to finish
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
            self._active_tasks.clear()
        self._logger.info("Workflow engine shutdown (%d tasks cancelled)", count)

    def get_waiting_run(
        self, chat_id: int, topic_id: int | None
    ) -> WorkflowRun | None:
        """Find a workflow run waiting for user reply in this chat."""
        return self._registry.get_waiting_run(chat_id, topic_id)

    # ── Main execution loop ─────────────────────────────────────────

    async def _execute_run(self, run_id: str) -> None:
        """Drive a workflow run to completion (or pause)."""
        try:
            while True:
                run = self._registry.get_run(run_id)
                if not run or run.status != WorkflowRunStatus.RUNNING:
                    break

                definition = self._registry.get_definition(run.workflow_id)
                if not definition:
                    break

                current_step = next(
                    (s for s in definition.steps if s.id == run.current_step_id),
                    None,
                )
                if not current_step:
                    # No more steps — workflow is done
                    run.status = WorkflowRunStatus.COMPLETED
                    run.completed_at = time.time()
                    self._registry.update_run(run)
                    break

                step_run = await self._execute_step(
                    current_step, run, definition
                )
                run.step_runs[current_step.id] = step_run

                # ── WAITING: pause engine ───────────────────────────
                if step_run.status == StepStatus.WAITING:
                    run.status = WorkflowRunStatus.WAITING
                    run.wait_step_id = current_step.id
                    self._registry.update_run(run)
                    break

                # ── FAILED: handle error strategy ───────────────────
                if step_run.status == StepStatus.FAILED:
                    should_break = await self._handle_step_failure(
                        current_step, step_run, run, definition
                    )
                    if should_break:
                        break
                    continue  # retry / fallback loop

                # ── SUCCESS / SKIPPED: advance to next step ─────────
                next_id = self._resolve_next_step(
                    current_step, definition, step_run=step_run
                )
                if next_id:
                    run.current_step_id = next_id
                    self._registry.update_run(run)
                else:
                    run.status = WorkflowRunStatus.COMPLETED
                    run.completed_at = time.time()
                    self._registry.update_run(run)
                    await self._notify(
                        run.chat_id,
                        run.topic_id,
                        run.transport,
                        f"Workflow **{definition.name}** completed successfully.",
                        run_id=run.run_id,
                        workflow_name=definition.name,
                    )
                    break

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._logger.exception("Workflow run %s failed", run_id)
            run = self._registry.get_run(run_id)
            if run:
                run.status = WorkflowRunStatus.FAILED
                run.error = str(exc)
                run.completed_at = time.time()
                self._registry.update_run(run)
        finally:
            self._active_tasks.pop(run_id, None)

    # ── Step execution ──────────────────────────────────────────────

    async def _execute_step(
        self,
        step: StepDefinition,
        run: WorkflowRun,
        definition: WorkflowDefinition,
    ) -> StepRun:
        """Execute a single step and return its StepRun."""
        sr = run.step_runs.get(step.id, StepRun(step_id=step.id))
        sr.status = StepStatus.RUNNING
        sr.started_at = time.time()

        try:
            prompt = resolve_variables(
                step.prompt or step.message, run.variables, run.step_runs
            )

            if step.type == StepType.ASK_AGENT:
                sr.output = await self._run_ask_agent(step, prompt)
                sr.status = StepStatus.COMPLETED

            elif step.type == StepType.NOTIFY:
                await self._notify(
                    run.chat_id, run.topic_id, run.transport, prompt,
                    run_id=run.run_id, workflow_name=definition.name,
                )
                sr.output = prompt
                sr.status = StepStatus.COMPLETED

            elif step.type == StepType.WAIT_FOR_REPLY:
                await self._notify(
                    run.chat_id, run.topic_id, run.transport, prompt,
                    run_id=run.run_id, workflow_name=definition.name,
                )
                sr.status = StepStatus.WAITING

            elif step.type == StepType.CONDITION:
                target = execute_condition(
                    step.if_expr,
                    run.variables,
                    run.step_runs,
                    then_step=step.then,
                    else_step=step.else_,
                )
                sr.output = target
                sr.status = StepStatus.COMPLETED

            elif step.type == StepType.PARALLEL:
                results = await execute_parallel(
                    step.steps,
                    lambda s: self._execute_step(s, run, definition),
                )
                sr.output = str(results)
                sr.status = StepStatus.COMPLETED

            else:
                raise WorkflowStepError(
                    f"Unsupported step type: {step.type}"
                )

        except WaitForReplySignal:
            sr.status = StepStatus.WAITING
        except asyncio.TimeoutError:
            sr.status = StepStatus.FAILED
            sr.error = f"Step timed out after {step.timeout}s"
        except WorkflowStepError as exc:
            sr.status = StepStatus.FAILED
            sr.error = str(exc)
        except Exception as exc:
            sr.status = StepStatus.FAILED
            sr.error = str(exc)

        if sr.status != StepStatus.WAITING:
            sr.completed_at = time.time()
        return sr

    async def _run_ask_agent(
        self, step: StepDefinition, prompt: str
    ) -> str:
        """Execute an ask_agent step with timeout."""
        timeout = step.timeout or self._default_step_timeout
        if self._ask_agent:
            return await asyncio.wait_for(
                self._ask_agent(
                    step.agent,
                    prompt,
                    timeout,
                    new_session=step.new_session,
                    provider=step.provider,
                    model=step.model,
                ),
                timeout=timeout,
            )
        return await asyncio.wait_for(
            execute_ask_agent(
                step.agent,
                prompt,
                timeout,
                new_session=step.new_session,
                provider=step.provider,
                model=step.model,
            ),
            timeout=timeout,
        )

    # ── Error handling ──────────────────────────────────────────────

    async def _handle_step_failure(
        self,
        step: StepDefinition,
        step_run: StepRun,
        run: WorkflowRun,
        definition: WorkflowDefinition,
    ) -> bool:
        """Handle a failed step according to its error strategy.

        Returns True if the run loop should break, False to continue.
        """
        error_action = step.on_error

        # ── RETRY ───────────────────────────────────────────────
        if error_action == ErrorAction.RETRY and step.retry:
            if step_run.attempt < step.retry.max_attempts:
                step_run.attempt += 1
                step_run.status = StepStatus.PENDING
                self._registry.update_run(run)  # persist before sleep
                await asyncio.sleep(step.retry.delay_seconds)
                return False  # continue loop, retry same step

        # ── FALLBACK ────────────────────────────────────────────
        if error_action == ErrorAction.FALLBACK and step.fallback:
            run.current_step_id = step.fallback.goto
            self._registry.update_run(run)
            return False  # continue loop at fallback step

        # ── SKIP ────────────────────────────────────────────────
        if error_action == ErrorAction.SKIP:
            step_run.status = StepStatus.SKIPPED
            next_id = self._resolve_next_step(step, definition)
            if next_id:
                run.current_step_id = next_id
                self._registry.update_run(run)
                return False
            # No next step — complete
            run.status = WorkflowRunStatus.COMPLETED
            run.completed_at = time.time()
            self._registry.update_run(run)
            return True

        # ── ABORT (default) ─────────────────────────────────────
        run.status = WorkflowRunStatus.FAILED
        run.error = step_run.error
        run.completed_at = time.time()
        self._registry.update_run(run)
        await self._notify(
            run.chat_id,
            run.topic_id,
            run.transport,
            f"Workflow **{definition.name}** failed at step "
            f"**{step.id}**: {step_run.error}",
            run_id=run.run_id,
            workflow_name=definition.name,
        )
        return True

    # ── Next-step resolution ────────────────────────────────────────

    def _resolve_next_step(
        self,
        current_step: StepDefinition | None,
        definition: WorkflowDefinition,
        *,
        step_run: StepRun | None = None,
    ) -> str | None:
        """Determine which step to execute next.

        Priority:
        1. Explicit ``goto`` on the step definition.
        2. Condition step output (then/else target).
        3. Sequential: next step in the definition list.
        """
        if current_step is None:
            return None

        # Explicit goto
        if current_step.goto:
            return current_step.goto

        # Condition step — output holds the target step_id
        if current_step.type == StepType.CONDITION and step_run and step_run.output:
            return step_run.output

        # Sequential
        step_ids = [s.id for s in definition.steps]
        try:
            idx = step_ids.index(current_step.id)
            if idx + 1 < len(step_ids):
                return step_ids[idx + 1]
        except ValueError:
            pass
        return None
