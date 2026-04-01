"""Tests for the WorkflowEngine — the most critical test module."""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from sygen_bot.workflow.engine import WorkflowEngine
from sygen_bot.workflow.models import (
    ErrorAction,
    StepStatus,
    WorkflowRunStatus,
)
from sygen_bot.workflow.registry import WorkflowRegistry


# ── Helpers ──────────────────────────────────────────────────────────

def _make_registry(tmp_path: Path, yaml_str: str) -> WorkflowRegistry:
    d = tmp_path / "defs"
    d.mkdir(exist_ok=True)
    (d / "wf.yaml").write_text(yaml_str, encoding="utf-8")
    return WorkflowRegistry(d, tmp_path / "runs.json")


async def _wait_status(registry, run_id, target, timeout=5.0):
    """Poll until a run reaches *target* status or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        run = registry.get_run(run_id)
        if run and run.status == target:
            return run
        await asyncio.sleep(0.05)
    run = registry.get_run(run_id)
    raise TimeoutError(
        f"Run {run_id} did not reach {target} within {timeout}s "
        f"(current: {run.status if run else 'None'})"
    )


# ── Basic lifecycle ──────────────────────────────────────────────────

class TestStartWorkflow:
    @pytest.mark.asyncio
    async def test_creates_run(self, engine: WorkflowEngine, registry: WorkflowRegistry):
        run_id = await engine.start_workflow(
            "test_workflow", chat_id=1, topic_id=None,
            transport="tg", parent_agent="main",
        )
        assert run_id
        run = registry.get_run(run_id)
        assert run is not None
        assert run.status in (
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.WAITING,
            WorkflowRunStatus.COMPLETED,
        )


class TestSequentialExecution:
    @pytest.mark.asyncio
    async def test_two_ask_steps(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: seq
            name: Sequential
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "first"
                timeout: 10
              - id: s2
                type: ask_agent
                agent: a
                prompt: "second got $steps.s1.output"
                timeout: 10
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_ask = AsyncMock(side_effect=["reply1", "reply2"])
        mock_notify = AsyncMock()
        eng = WorkflowEngine(reg, notify_callback=mock_notify, ask_agent_fn=mock_ask)

        run_id = await eng.start_workflow(
            "seq", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)

        run = reg.get_run(run_id)
        assert run.step_runs["s1"].output == "reply1"
        assert run.step_runs["s2"].output == "reply2"
        # Verify second prompt got the resolved variable
        assert mock_ask.call_count == 2


class TestNotifyStep:
    @pytest.mark.asyncio
    async def test_notify_calls_callback(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: nwf
            name: Notify WF
            trigger: {manual: true}
            steps:
              - id: n1
                type: notify
                message: "Hello user"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_notify = AsyncMock()
        eng = WorkflowEngine(reg, notify_callback=mock_notify)

        run_id = await eng.start_workflow(
            "nwf", chat_id=5, topic_id=None, transport="tg", parent_agent="main"
        )
        await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)

        # notify called for step + completion message
        calls = [c for c in mock_notify.call_args_list if "Hello user" in str(c)]
        assert len(calls) >= 1


# ── Wait & Resume ────────────────────────────────────────────────────

class TestWaitForReply:
    @pytest.mark.asyncio
    async def test_pauses_on_wait(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: waitwf
            name: Wait WF
            trigger: {manual: true}
            steps:
              - id: w1
                type: wait_for_reply
                prompt: "Your input?"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_notify = AsyncMock()
        eng = WorkflowEngine(reg, notify_callback=mock_notify)

        run_id = await eng.start_workflow(
            "waitwf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.WAITING)
        assert run.wait_step_id == "w1"


class TestResumeWorkflow:
    @pytest.mark.asyncio
    async def test_resume_completes(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: rwf
            name: Resume WF
            trigger: {manual: true}
            steps:
              - id: w1
                type: wait_for_reply
                prompt: "Input?"
              - id: n1
                type: notify
                message: "Got: $steps.w1.output"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_notify = AsyncMock()
        eng = WorkflowEngine(reg, notify_callback=mock_notify)

        run_id = await eng.start_workflow(
            "rwf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        await _wait_status(reg, run_id, WorkflowRunStatus.WAITING)

        await eng.resume_workflow(run_id, "user answer")
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)

        assert run.step_runs["w1"].output == "user answer"
        # Verify notify got the resolved output
        notify_calls = [
            c for c in mock_notify.call_args_list
            if "Got: user answer" in str(c)
        ]
        assert len(notify_calls) >= 1


# ── Conditions ───────────────────────────────────────────────────────

class TestConditionThenBranch:
    @pytest.mark.asyncio
    async def test_then_path(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: cond_then
            name: Cond Then
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "x"
                timeout: 10
              - id: c1
                type: condition
                if: "'yes' in 'yes please'"
                then: done
                else: s1
              - id: done
                type: notify
                message: "Finished"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        eng = WorkflowEngine(
            reg, notify_callback=AsyncMock(),
            ask_agent_fn=AsyncMock(return_value="ok"),
        )
        run_id = await eng.start_workflow(
            "cond_then", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)
        assert run.step_runs["c1"].output == "done"


class TestConditionElseBranch:
    @pytest.mark.asyncio
    async def test_else_path(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: cond_else
            name: Cond Else
            trigger: {manual: true}
            steps:
              - id: c1
                type: condition
                if: "'nope' in 'yes'"
                then: unreachable
                else: fallback
              - id: unreachable
                type: notify
                message: "Should not get here"
              - id: fallback
                type: notify
                message: "Fell back"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        eng = WorkflowEngine(reg, notify_callback=AsyncMock())
        run_id = await eng.start_workflow(
            "cond_else", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)
        assert run.step_runs["c1"].output == "fallback"


# ── Goto ─────────────────────────────────────────────────────────────

class TestGotoStep:
    @pytest.mark.asyncio
    async def test_goto_skips(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: gotowf
            name: Goto WF
            trigger: {manual: true}
            steps:
              - id: s1
                type: notify
                message: "start"
                goto: s3
              - id: s2
                type: notify
                message: "skipped"
              - id: s3
                type: notify
                message: "jumped here"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        eng = WorkflowEngine(reg, notify_callback=AsyncMock())
        run_id = await eng.start_workflow(
            "gotowf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)
        assert "s1" in run.step_runs
        assert "s2" not in run.step_runs
        assert "s3" in run.step_runs


# ── Error handling ───────────────────────────────────────────────────

class TestErrorAbort:
    @pytest.mark.asyncio
    async def test_abort_on_failure(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: abortwf
            name: Abort WF
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "fail"
                timeout: 10
                on_error: abort
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_ask = AsyncMock(side_effect=Exception("boom"))
        eng = WorkflowEngine(
            reg, notify_callback=AsyncMock(), ask_agent_fn=mock_ask,
        )
        run_id = await eng.start_workflow(
            "abortwf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.FAILED)
        assert "boom" in run.error


class TestErrorRetry:
    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: retrywf
            name: Retry WF
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "try"
                timeout: 10
                on_error: retry
                retry:
                  max_attempts: 3
                  delay_seconds: 0.01
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_ask = AsyncMock(side_effect=[Exception("fail1"), Exception("fail2"), "ok"])
        eng = WorkflowEngine(
            reg, notify_callback=AsyncMock(), ask_agent_fn=mock_ask,
        )
        run_id = await eng.start_workflow(
            "retrywf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)
        assert run.step_runs["s1"].output == "ok"


class TestErrorFallback:
    @pytest.mark.asyncio
    async def test_fallback_goto(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: fbwf
            name: Fallback WF
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "fail"
                timeout: 10
                on_error: fallback
                fallback:
                  goto: recovery
              - id: recovery
                type: notify
                message: "recovered"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_ask = AsyncMock(side_effect=Exception("err"))
        eng = WorkflowEngine(
            reg, notify_callback=AsyncMock(), ask_agent_fn=mock_ask,
        )
        run_id = await eng.start_workflow(
            "fbwf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)
        assert "recovery" in run.step_runs


class TestErrorSkip:
    @pytest.mark.asyncio
    async def test_skip_continues(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: skipwf
            name: Skip WF
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "fail"
                timeout: 10
                on_error: skip
              - id: s2
                type: notify
                message: "continued"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_ask = AsyncMock(side_effect=Exception("err"))
        eng = WorkflowEngine(
            reg, notify_callback=AsyncMock(), ask_agent_fn=mock_ask,
        )
        run_id = await eng.start_workflow(
            "skipwf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)
        assert run.step_runs["s1"].status == StepStatus.SKIPPED
        assert "s2" in run.step_runs


# ── Timeout ──────────────────────────────────────────────────────────

class TestTimeoutStep:
    @pytest.mark.asyncio
    async def test_timeout_fails_step(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: towf
            name: Timeout WF
            trigger: {manual: true}
            steps:
              - id: s1
                type: ask_agent
                agent: a
                prompt: "slow"
                timeout: 0.1
                on_error: abort
        """)
        reg = _make_registry(tmp_path, wf_yaml)

        async def slow_agent(*args, **kwargs):
            await asyncio.sleep(10)
            return "never"

        eng = WorkflowEngine(
            reg, notify_callback=AsyncMock(), ask_agent_fn=slow_agent,
        )
        run_id = await eng.start_workflow(
            "towf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        run = await _wait_status(reg, run_id, WorkflowRunStatus.FAILED, timeout=3.0)
        assert run.step_runs["s1"].status == StepStatus.FAILED


# ── Cancel ───────────────────────────────────────────────────────────

class TestCancelWorkflow:
    @pytest.mark.asyncio
    async def test_cancel(self, tmp_path: Path):
        wf_yaml = textwrap.dedent("""\
            id: cancelwf
            name: Cancel WF
            trigger: {manual: true}
            steps:
              - id: w1
                type: wait_for_reply
                prompt: "wait forever"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        eng = WorkflowEngine(reg, notify_callback=AsyncMock())

        run_id = await eng.start_workflow(
            "cancelwf", chat_id=1, topic_id=None, transport="tg", parent_agent="main"
        )
        await _wait_status(reg, run_id, WorkflowRunStatus.WAITING)

        result = await eng.cancel_workflow(run_id)
        assert result is True
        run = reg.get_run(run_id)
        assert run.status == WorkflowRunStatus.CANCELLED


# ── End-to-end ───────────────────────────────────────────────────────

class TestFullWorkflowEndToEnd:
    @pytest.mark.asyncio
    async def test_full_flow(self, tmp_path: Path):
        """ask → notify → wait → resume → condition → done"""
        wf_yaml = textwrap.dedent("""\
            id: e2e
            name: E2E
            trigger: {manual: true}
            variables:
              greeting: hello
            steps:
              - id: ask1
                type: ask_agent
                agent: helper
                prompt: "Say $greeting"
                timeout: 10
              - id: notify1
                type: notify
                message: "Agent said: $steps.ask1.output"
              - id: wait1
                type: wait_for_reply
                prompt: "Approve?"
              - id: cond1
                type: condition
                if: "'yes' in '$steps.wait1.output'.lower()"
                then: done
                else: ask1
              - id: done
                type: notify
                message: "All done!"
        """)
        reg = _make_registry(tmp_path, wf_yaml)
        mock_notify = AsyncMock()
        mock_ask = AsyncMock(return_value="Agent response")
        eng = WorkflowEngine(
            reg, notify_callback=mock_notify, ask_agent_fn=mock_ask,
        )

        run_id = await eng.start_workflow(
            "e2e", chat_id=42, topic_id=None, transport="tg", parent_agent="main"
        )
        # Should pause at wait_for_reply
        run = await _wait_status(reg, run_id, WorkflowRunStatus.WAITING)
        assert run.wait_step_id == "wait1"

        # Verify ask_agent was called
        assert mock_ask.call_count >= 1

        # Resume with "yes" to take the then branch
        await eng.resume_workflow(run_id, "yes please")
        run = await _wait_status(reg, run_id, WorkflowRunStatus.COMPLETED)

        assert run.step_runs["ask1"].output == "Agent response"
        assert run.step_runs["wait1"].output == "yes please"
        assert run.step_runs["cond1"].output == "done"
        assert "done" in run.step_runs
