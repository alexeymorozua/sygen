"""Tests for the message hook system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sygen_bot.cli.types import AgentResponse
from sygen_bot.orchestrator.core import Orchestrator
from sygen_bot.orchestrator.flows import normal
from sygen_bot.orchestrator.hooks import (
    MAINMEMORY_REMINDER,
    _MODULE_LINE_LIMIT,
    _check_module_sizes,
    HookContext,
    MessageHook,
    MessageHookRegistry,
    every_n_messages,
)
from sygen_bot.session.key import SessionKey

# ---------------------------------------------------------------------------
# Unit tests: HookContext, conditions, registry
# ---------------------------------------------------------------------------


def _ctx(*, message_count: int = 0, is_new: bool = False) -> HookContext:
    return HookContext(
        chat_id=1,
        message_count=message_count,
        is_new_session=is_new,
        provider="claude",
        model="opus",
    )


class TestEveryNMessages:
    def test_fires_on_nth_message(self) -> None:
        check = every_n_messages(6)
        # message_count is pre-increment: count=5 -> 6th message
        assert check(_ctx(message_count=5)) is True

    def test_fires_on_multiples(self) -> None:
        check = every_n_messages(6)
        assert check(_ctx(message_count=11)) is True  # 12th
        assert check(_ctx(message_count=17)) is True  # 18th

    def test_does_not_fire_on_first(self) -> None:
        check = every_n_messages(6)
        assert check(_ctx(message_count=0)) is False

    def test_does_not_fire_between_intervals(self) -> None:
        check = every_n_messages(6)
        for count in (1, 2, 3, 4, 6, 7, 8, 9, 10):
            assert check(_ctx(message_count=count)) is False

    def test_interval_of_1(self) -> None:
        check = every_n_messages(1)
        assert check(_ctx(message_count=0)) is True
        assert check(_ctx(message_count=1)) is True
        assert check(_ctx(message_count=99)) is True

    def test_interval_of_3(self) -> None:
        check = every_n_messages(3)
        assert check(_ctx(message_count=2)) is True  # 3rd
        assert check(_ctx(message_count=5)) is True  # 6th
        assert check(_ctx(message_count=1)) is False
        assert check(_ctx(message_count=3)) is False


class TestMessageHookRegistry:
    def test_no_hooks_returns_original(self) -> None:
        reg = MessageHookRegistry()
        assert reg.apply("hello", _ctx()) == "hello"

    def test_matching_hook_appends_suffix(self) -> None:
        reg = MessageHookRegistry()
        hook = MessageHook(name="test", condition=lambda _: True, suffix="## Reminder")
        reg.register(hook)
        result = reg.apply("hello", _ctx())
        assert result == "hello\n\n## Reminder"

    def test_non_matching_hook_ignored(self) -> None:
        reg = MessageHookRegistry()
        hook = MessageHook(name="test", condition=lambda _: False, suffix="## Reminder")
        reg.register(hook)
        assert reg.apply("hello", _ctx()) == "hello"

    def test_multiple_hooks_concatenated(self) -> None:
        reg = MessageHookRegistry()
        reg.register(MessageHook(name="a", condition=lambda _: True, suffix="A"))
        reg.register(MessageHook(name="b", condition=lambda _: True, suffix="B"))
        result = reg.apply("hello", _ctx())
        assert result == "hello\n\nA\n\nB"

    def test_mixed_matching(self) -> None:
        reg = MessageHookRegistry()
        reg.register(MessageHook(name="yes", condition=lambda _: True, suffix="YES"))
        reg.register(MessageHook(name="no", condition=lambda _: False, suffix="NO"))
        result = reg.apply("hello", _ctx())
        assert result == "hello\n\nYES"
        assert "NO" not in result


class TestMainmemoryReminder:
    def test_fires_on_6th(self) -> None:
        assert MAINMEMORY_REMINDER.condition(_ctx(message_count=5)) is True

    def test_does_not_fire_on_5th(self) -> None:
        assert MAINMEMORY_REMINDER.condition(_ctx(message_count=4)) is False

    def test_suffix_contains_key_phrases(self) -> None:
        ctx = _ctx(message_count=5)
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx)
        assert "MAINMEMORY.md" in resolved
        assert "MEMORY CHECK" in resolved
        assert "First answer the user's message fully" in resolved


class TestSuffixFn:
    def test_suffix_fn_takes_precedence(self) -> None:
        hook = MessageHook(
            name="test",
            condition=lambda _: True,
            suffix="static",
            suffix_fn=lambda ctx: "dynamic",
        )
        assert hook.resolve_suffix(_ctx()) == "dynamic"

    def test_falls_back_to_suffix(self) -> None:
        hook = MessageHook(name="test", condition=lambda _: True, suffix="static")
        assert hook.resolve_suffix(_ctx()) == "static"

    def test_registry_uses_resolve_suffix(self) -> None:
        reg = MessageHookRegistry()
        reg.register(
            MessageHook(
                name="dyn",
                condition=lambda _: True,
                suffix_fn=lambda ctx: f"count={ctx.message_count}",
            )
        )
        result = reg.apply("hello", _ctx(message_count=42))
        assert "count=42" in result


class TestMainmemoryReminderInjectsModules:
    """MAINMEMORY_REMINDER should inject Always Load module content."""

    def test_injects_module_content(self, tmp_path: Path) -> None:
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "user.md").write_text("Name: Alex\nRole: Developer")
        (modules_dir / "decisions.md").write_text("Rule 1: tests required")
        mainmemory = tmp_path / "MAINMEMORY.md"
        mainmemory.write_text(
            "### Always Load\n"
            "| M | D | P |\n"
            "| user | Profile | [modules/user.md](modules/user.md) |\n"
            "| decisions | Rules | [modules/decisions.md](modules/decisions.md) |\n"
            "### Load On Demand\n"
        )
        ctx = HookContext(
            chat_id=1, message_count=5, is_new_session=False,
            provider="claude", model="opus", memory_modules_dir=modules_dir,
        )
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx)
        assert "Name: Alex" in resolved
        assert "Rule 1: tests required" in resolved

    def test_truncates_long_modules_default(self, tmp_path: Path) -> None:
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        long_content = "\n".join(f"Line {i}" for i in range(50))
        (modules_dir / "user.md").write_text(long_content)
        mainmemory = tmp_path / "MAINMEMORY.md"
        mainmemory.write_text("")  # no Always Load section -> defaults
        ctx = HookContext(
            chat_id=1, message_count=5, is_new_session=False,
            provider="claude", model="opus", memory_modules_dir=modules_dir,
        )
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx)
        # Default hook_compact_lines=20
        assert "Line 19" in resolved
        assert "[...]" in resolved
        assert "Line 20" not in resolved

    def test_truncates_with_custom_limit(self, tmp_path: Path) -> None:
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        long_content = "\n".join(f"Line {i}" for i in range(50))
        (modules_dir / "user.md").write_text(long_content)
        mainmemory = tmp_path / "MAINMEMORY.md"
        mainmemory.write_text("")
        ctx = HookContext(
            chat_id=1, message_count=5, is_new_session=False,
            provider="claude", model="opus", memory_modules_dir=modules_dir,
            hook_compact_lines=10,
        )
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx)
        assert "Line 9" in resolved
        assert "[...]" in resolved
        assert "Line 10" not in resolved

    def test_no_modules_dir_still_works(self) -> None:
        ctx = HookContext(
            chat_id=1, message_count=5, is_new_session=False,
            provider="claude", model="opus", memory_modules_dir=None,
        )
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx)
        assert "MEMORY CHECK" in resolved
        # No crash, no module content
        assert "# Memory:" not in resolved

    def test_inject_all_modules(self, tmp_path: Path) -> None:
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "user.md").write_text("User data")
        (modules_dir / "infra.md").write_text("Server info")
        mainmemory = tmp_path / "MAINMEMORY.md"
        # Only user.md in Always Load
        mainmemory.write_text(
            "### Always Load\n"
            "| M | D | P |\n"
            "| user | Profile | [modules/user.md](modules/user.md) |\n"
            "### Load On Demand\n"
        )
        # With inject_all_modules=False: only user.md
        ctx_selective = HookContext(
            chat_id=1, message_count=5, is_new_session=False,
            provider="claude", model="opus", memory_modules_dir=modules_dir,
            inject_all_modules=False,
        )
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx_selective)
        assert "User data" in resolved
        assert "Server info" not in resolved

        # With inject_all_modules=True: both modules
        ctx_all = HookContext(
            chat_id=1, message_count=5, is_new_session=False,
            provider="claude", model="opus", memory_modules_dir=modules_dir,
            inject_all_modules=True,
        )
        resolved_all = MAINMEMORY_REMINDER.resolve_suffix(ctx_all)
        assert "User data" in resolved_all
        assert "Server info" in resolved_all


class TestCheckModuleSizes:
    def test_no_dir_returns_empty(self) -> None:
        assert _check_module_sizes(None) == ""
        assert _check_module_sizes(Path("/nonexistent")) == ""

    def test_under_limit_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "small.md").write_text("line\n" * 50)
        assert _check_module_sizes(tmp_path) == ""

    def test_over_limit_returns_warning(self, tmp_path: Path) -> None:
        (tmp_path / "big.md").write_text("line\n" * 150)
        result = _check_module_sizes(tmp_path)
        assert "big.md" in result
        assert "150 lines" in result
        assert f"limit {_MODULE_LINE_LIMIT}" in result

    def test_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "ok.md").write_text("line\n" * 50)
        (tmp_path / "big1.md").write_text("line\n" * 130)
        (tmp_path / "big2.md").write_text("line\n" * 200)
        result = _check_module_sizes(tmp_path)
        assert "big1.md" in result
        assert "big2.md" in result
        assert "ok.md" not in result

    def test_mainmemory_hook_includes_size_warning(self, tmp_path: Path) -> None:
        (tmp_path / "decisions.md").write_text("line\n" * 150)
        ctx = _ctx(message_count=5)
        ctx_with_dir = HookContext(
            chat_id=ctx.chat_id,
            message_count=ctx.message_count,
            is_new_session=ctx.is_new_session,
            provider=ctx.provider,
            model=ctx.model,
            memory_modules_dir=tmp_path,
        )
        resolved = MAINMEMORY_REMINDER.resolve_suffix(ctx_with_dir)
        assert "consolidate now" in resolved
        assert "decisions.md" in resolved
        assert "150 lines" in resolved


# ---------------------------------------------------------------------------
# Integration: hook fires through the full flow
# ---------------------------------------------------------------------------


def _mock_response(**kwargs: object) -> AgentResponse:
    defaults: dict[str, object] = {
        "result": "OK",
        "session_id": "sess-123",
        "is_error": False,
        "cost_usd": 0.01,
        "total_tokens": 100,
    }
    defaults.update(kwargs)
    return AgentResponse(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def orch(orch: Orchestrator) -> Orchestrator:
    return orch


async def test_hook_injects_into_prompt_on_6th_message(orch: Orchestrator) -> None:
    """After 5 successful messages, the 6th should carry the reminder."""
    resp = _mock_response()
    mock_execute = AsyncMock(return_value=resp)
    object.__setattr__(orch._cli_service, "execute", mock_execute)

    # Send 5 messages to build up the counter
    for _ in range(5):
        await normal(orch, SessionKey(chat_id=1), "msg")

    # 6th message should have the hook injected
    await normal(orch, SessionKey(chat_id=1), "sixth")

    sixth_call = mock_execute.call_args_list[5]
    request = sixth_call[0][0]
    assert "MEMORY CHECK" in request.prompt
    assert "memory_system/MAINMEMORY.md" in request.prompt


async def test_hook_not_injected_before_6th(orch: Orchestrator) -> None:
    """Messages 1-5 should not carry the mainmemory reminder."""
    resp = _mock_response()
    mock_execute = AsyncMock(return_value=resp)
    object.__setattr__(orch._cli_service, "execute", mock_execute)

    for i in range(5):
        await normal(orch, SessionKey(chat_id=1), f"msg-{i}")
        request = mock_execute.call_args_list[i][0][0]
        assert "MEMORY CHECK" not in request.prompt


async def test_hook_resets_on_new_session(orch: Orchestrator) -> None:
    """After session reset, counter restarts -- 6th from reset triggers hook."""
    resp = _mock_response()
    mock_execute = AsyncMock(return_value=resp)
    object.__setattr__(orch._cli_service, "execute", mock_execute)

    # Send 5 messages
    for _ in range(5):
        await normal(orch, SessionKey(chat_id=1), "msg")

    # Reset session (simulates /new)
    await orch._sessions.reset_session(SessionKey(chat_id=1))

    # Messages after reset should NOT carry the mainmemory reminder (counter back to 0)
    # (DELEGATION_BRIEF fires on new session, but that's expected and correct)
    await normal(orch, SessionKey(chat_id=1), "after-reset")
    last_request = mock_execute.call_args[0][0]
    assert "MEMORY CHECK" not in last_request.prompt
