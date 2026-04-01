"""Step executors for the workflow engine.

Each step type has a dedicated async function that handles its execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Awaitable

import aiohttp

from sygen_bot.workflow.models import StepRun
from sygen_bot.workflow.variables import resolve_variables, safe_eval

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────


class WorkflowStepError(Exception):
    """Raised when a workflow step fails in a recoverable way."""


class WaitForReplySignal(Exception):
    """Raised to pause workflow execution until a user reply arrives."""

    def __init__(self, step_id: str) -> None:
        self.step_id = step_id
        super().__init__(f"Waiting for reply on step {step_id}")


# ── ASK_AGENT executor ─────────────────────────────────────────────


async def execute_ask_agent(
    agent: str,
    prompt: str,
    timeout: float,
    *,
    new_session: bool = True,
    provider: str = "",
    model: str = "",
    bus: Any = None,
    port: int = 8080,
) -> str:
    """Send a prompt to another agent and return its text response.

    If *bus* (InterAgentBus) is provided, uses it directly.
    Otherwise falls back to an HTTP POST to the internal API.
    """
    if bus is not None:
        try:
            result = await bus.send(
                agent,
                prompt,
                new_session=new_session,
                provider=provider,
                model=model,
            )
            return str(result)
        except Exception as exc:
            raise WorkflowStepError(
                f"InterAgentBus.send to '{agent}' failed: {exc}"
            ) from exc

    # HTTP fallback
    url = f"http://127.0.0.1:{port}/agents/ask"
    payload: dict[str, Any] = {
        "agent": agent,
        "prompt": prompt,
        "new_session": new_session,
    }
    if provider:
        payload["provider"] = provider
    if model:
        payload["model"] = model

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise WorkflowStepError(
                        f"ask_agent HTTP {resp.status}: {body}"
                    )
                data = await resp.json()
                return str(data.get("response", data.get("result", "")))
    except aiohttp.ClientError as exc:
        raise WorkflowStepError(
            f"ask_agent HTTP request to '{agent}' failed: {exc}"
        ) from exc
    except asyncio.TimeoutError as exc:
        raise WorkflowStepError(
            f"ask_agent request to '{agent}' timed out after {timeout}s"
        ) from exc


# ── NOTIFY executor ────────────────────────────────────────────────


async def execute_notify(
    message: str,
    chat_id: int,
    topic_id: int | None,
    transport: str,
    *,
    callback: Callable[..., Awaitable[Any]],
) -> str:
    """Send a notification message via the provided callback.

    The callback signature is:
        async callback(chat_id, topic_id, transport, message)
    """
    try:
        await callback(chat_id, topic_id, transport, message)
    except Exception as exc:
        raise WorkflowStepError(f"Notify failed: {exc}") from exc
    return message


# ── WAIT_FOR_REPLY executor ────────────────────────────────────────


async def execute_wait_for_reply(step_id: str) -> None:
    """Signal the engine to pause and wait for user input."""
    raise WaitForReplySignal(step_id)


# ── CONDITION executor ─────────────────────────────────────────────


def execute_condition(
    if_expr: str,
    variables: dict[str, Any],
    step_runs: dict[str, StepRun],
    *,
    then_step: str = "",
    else_step: str = "",
) -> str:
    """Evaluate a condition and return the target step id.

    1. Resolve variable references in *if_expr*.
    2. Evaluate the expression with safe_eval.
    3. Return *then_step* if truthy, *else_step* otherwise.
    """
    resolved = resolve_variables(if_expr, variables, step_runs)
    result = safe_eval(resolved)
    return then_step if result else else_step


# ── PARALLEL executor ──────────────────────────────────────────────


async def execute_parallel(
    steps: list[Any],
    execute_fn: Callable[..., Awaitable[Any]],
) -> dict[str, Any]:
    """Run multiple steps concurrently and collect results.

    *execute_fn* is called for each step; it should return a StepRun or
    similar object with ``step_id`` and ``output`` attributes.

    Returns a dict mapping step_id -> output string.
    """
    # Validate: wait_for_reply is not allowed inside parallel blocks
    for s in steps:
        if hasattr(s, "type") and s.type == "wait_for_reply":
            raise WorkflowStepError(
                f"wait_for_reply step '{getattr(s, 'id', s)}' cannot be used inside a parallel block"
            )

    tasks = [execute_fn(s) for s in steps]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, Any] = {}
    for step, result in zip(steps, results):
        step_id = getattr(step, "id", str(step))
        if isinstance(result, WaitForReplySignal):
            raise WorkflowStepError(
                f"wait_for_reply step '{step_id}' cannot be used inside a parallel block"
            )
        if isinstance(result, Exception):
            logger.warning("Parallel step %s failed: %s", step_id, result)
            output[step_id] = f"ERROR: {result}"
        elif hasattr(result, "output"):
            output[step_id] = result.output
        else:
            output[step_id] = str(result)

    errors = {sid: msg for sid, msg in output.items() if isinstance(msg, str) and msg.startswith("ERROR:")}
    if errors:
        output["_warnings"] = f"{len(errors)} parallel step(s) failed: {', '.join(errors.keys())}"
    return output
