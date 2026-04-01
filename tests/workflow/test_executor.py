"""Tests for individual step executors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sygen_bot.workflow.executor import (
    WaitForReplySignal,
    WorkflowStepError,
    execute_ask_agent,
    execute_condition,
    execute_notify,
    execute_wait_for_reply,
)
from sygen_bot.workflow.models import StepRun, StepStatus


class TestExecuteAskAgentSuccess:
    @pytest.mark.asyncio
    async def test_via_bus(self):
        bus = MagicMock()
        bus.send = AsyncMock(return_value="bus reply")
        result = await execute_ask_agent(
            agent="helper", prompt="hi", timeout=10, bus=bus,
        )
        assert result == "bus reply"
        bus.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bus_called_with_args(self):
        bus = MagicMock()
        bus.send = AsyncMock(return_value="ok")
        await execute_ask_agent(
            agent="bot", prompt="test", timeout=5,
            new_session=False, provider="openai", model="gpt-4", bus=bus,
        )
        bus.send.assert_awaited_once_with(
            "bot", "test",
            new_session=False, provider="openai", model="gpt-4",
        )


class TestExecuteAskAgentError:
    @pytest.mark.asyncio
    async def test_bus_error_raises(self):
        bus = MagicMock()
        bus.send = AsyncMock(side_effect=RuntimeError("down"))
        with pytest.raises(WorkflowStepError, match="failed"):
            await execute_ask_agent(
                agent="helper", prompt="hi", timeout=10, bus=bus,
            )


class TestExecuteNotify:
    @pytest.mark.asyncio
    async def test_calls_callback(self):
        cb = AsyncMock()
        result = await execute_notify(
            message="hello", chat_id=1, topic_id=None,
            transport="tg", callback=cb,
        )
        assert result == "hello"
        cb.assert_awaited_once_with(1, None, "tg", "hello")

    @pytest.mark.asyncio
    async def test_callback_error(self):
        cb = AsyncMock(side_effect=RuntimeError("send failed"))
        with pytest.raises(WorkflowStepError, match="Notify failed"):
            await execute_notify(
                message="hi", chat_id=1, topic_id=None,
                transport="tg", callback=cb,
            )


class TestExecuteWaitForReply:
    @pytest.mark.asyncio
    async def test_raises_signal(self):
        with pytest.raises(WaitForReplySignal) as exc_info:
            await execute_wait_for_reply("step_x")
        assert exc_info.value.step_id == "step_x"


class TestExecuteConditionTrue:
    def test_simple_true(self):
        result = execute_condition(
            if_expr="'hello' in 'hello world'",
            variables={},
            step_runs={},
            then_step="yes_step",
            else_step="no_step",
        )
        assert result == "yes_step"

    def test_with_variable_resolution(self):
        sr = StepRun(step_id="s1", output="yes", status=StepStatus.COMPLETED)
        result = execute_condition(
            if_expr="'yes' in '$steps.s1.output'",
            variables={},
            step_runs={"s1": sr},
            then_step="approved",
            else_step="denied",
        )
        assert result == "approved"


class TestExecuteConditionFalse:
    def test_simple_false(self):
        result = execute_condition(
            if_expr="'x' in 'abc'",
            variables={},
            step_runs={},
            then_step="yes_step",
            else_step="no_step",
        )
        assert result == "no_step"

    def test_with_step_output_false(self):
        sr = StepRun(step_id="s1", output="no way", status=StepStatus.COMPLETED)
        result = execute_condition(
            if_expr="'yes' in '$steps.s1.output'",
            variables={},
            step_runs={"s1": sr},
            then_step="approved",
            else_step="denied",
        )
        assert result == "denied"
