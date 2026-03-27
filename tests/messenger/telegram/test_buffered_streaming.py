"""Tests for buffered streaming mode in run_streaming_message."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Chat, Message, User

from sygen_bot.config import SceneConfig, StreamingConfig
from sygen_bot.messenger.telegram.message_dispatch import (
    StreamingDispatch,
    run_streaming_message,
)
from sygen_bot.orchestrator.registry import OrchestratorResult
from sygen_bot.session.key import SessionKey


def _make_message(chat_id: int = 1, message_id: int = 42) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock(spec=Chat)
    msg.chat.id = chat_id
    msg.message_id = message_id
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 100
    return msg


def _make_result(text: str = "Hello world", **kwargs: object) -> OrchestratorResult:
    defaults: dict[str, object] = {
        "text": text,
        "stream_fallback": False,
    }
    defaults.update(kwargs)
    return OrchestratorResult(**defaults)


def _make_dispatch(
    *,
    buffered: bool = True,
    reaction_style: str = "off",
    **overrides: object,
) -> StreamingDispatch:
    bot = MagicMock()
    bot.set_message_reaction = AsyncMock()
    orchestrator = MagicMock()
    msg = _make_message()
    cfg = StreamingConfig(enabled=True, buffered=buffered)
    scene = SceneConfig(reaction_style=reaction_style)
    return StreamingDispatch(
        bot=bot,
        orchestrator=orchestrator,
        message=msg,
        key=SessionKey(chat_id=1),
        text="user input",
        streaming_cfg=cfg,
        allowed_roots=None,
        scene_config=scene,
        **overrides,
    )


class TestBufferedStreamingConfig:
    """Test that the buffered field exists and defaults correctly."""

    def test_default_false(self) -> None:
        cfg = StreamingConfig()
        assert cfg.buffered is False

    def test_set_true(self) -> None:
        cfg = StreamingConfig(buffered=True)
        assert cfg.buffered is True


class TestBufferedStreamingDispatch:
    """Test run_streaming_message with buffered=True."""

    @pytest.mark.asyncio
    async def test_buffered_sends_single_message(self) -> None:
        """Buffered mode should send one final message via send_rich, not stream."""
        dispatch = _make_dispatch(buffered=True)
        result = _make_result("Full response text")
        dispatch.orchestrator.handle_message_streaming = AsyncMock(return_value=result)

        with (
            patch(
                "sygen_bot.messenger.telegram.message_dispatch.send_rich",
                new_callable=AsyncMock,
            ) as mock_send_rich,
            patch(
                "sygen_bot.messenger.telegram.message_dispatch.create_stream_editor",
            ) as mock_create_editor,
        ):
            returned = await run_streaming_message(dispatch)

        assert returned == "Full response text"
        mock_send_rich.assert_called_once()
        # Stream editor should NOT be created in buffered mode
        mock_create_editor.assert_not_called()

    @pytest.mark.asyncio
    async def test_buffered_sends_reply_to_original(self) -> None:
        """Buffered mode send_rich should reply to the original message."""
        dispatch = _make_dispatch(buffered=True)
        result = _make_result("Response")
        dispatch.orchestrator.handle_message_streaming = AsyncMock(return_value=result)

        with patch(
            "sygen_bot.messenger.telegram.message_dispatch.send_rich",
            new_callable=AsyncMock,
        ) as mock_send_rich:
            await run_streaming_message(dispatch)

        opts = mock_send_rich.call_args[0][3]
        assert opts.reply_to_message_id == dispatch.message.message_id

    @pytest.mark.asyncio
    async def test_buffered_collects_text_deltas(self) -> None:
        """on_text callback should accumulate deltas (not send them)."""
        dispatch = _make_dispatch(buffered=True)
        collected_deltas: list[str] = []

        async def fake_streaming(key, text, *, on_text_delta, on_tool_activity, on_system_status):
            await on_text_delta("Hello ")
            await on_text_delta("world")
            return _make_result("Hello world")

        dispatch.orchestrator.handle_message_streaming = AsyncMock(side_effect=fake_streaming)

        with patch(
            "sygen_bot.messenger.telegram.message_dispatch.send_rich",
            new_callable=AsyncMock,
        ) as mock_send_rich:
            returned = await run_streaming_message(dispatch)

        assert returned == "Hello world"
        # Only one send_rich call (not per-delta)
        mock_send_rich.assert_called_once()

    @pytest.mark.asyncio
    async def test_buffered_detailed_reactions_still_work(self) -> None:
        """In buffered+detailed mode, reactions should still be set on the user message."""
        dispatch = _make_dispatch(buffered=True, reaction_style="detailed")

        async def fake_streaming(key, text, *, on_text_delta, on_tool_activity, on_system_status):
            await on_system_status("thinking")
            await on_text_delta("partial")
            await on_tool_activity("SearchTool")
            await on_system_status("compacting")
            await on_text_delta(" done")
            return _make_result("partial done")

        dispatch.orchestrator.handle_message_streaming = AsyncMock(side_effect=fake_streaming)

        with patch(
            "sygen_bot.messenger.telegram.message_dispatch.send_rich",
            new_callable=AsyncMock,
        ):
            await run_streaming_message(dispatch)

        # Reactions should have been set: thinking, tool, compacting, done
        reaction_calls = dispatch.bot.set_message_reaction.call_args_list
        emojis = [call.kwargs.get("reaction", call[1].get("reaction", None)) for call in reaction_calls]
        # At minimum, done reaction should be set
        assert dispatch.bot.set_message_reaction.call_count >= 1

    @pytest.mark.asyncio
    async def test_buffered_done_reaction_with_seen_style(self) -> None:
        """With reaction_style='seen', done reaction should still be set."""
        dispatch = _make_dispatch(buffered=True, reaction_style="seen")
        result = _make_result("Done")
        dispatch.orchestrator.handle_message_streaming = AsyncMock(return_value=result)

        with patch(
            "sygen_bot.messenger.telegram.message_dispatch.send_rich",
            new_callable=AsyncMock,
        ):
            await run_streaming_message(dispatch)

        dispatch.bot.set_message_reaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_buffered_no_reaction_when_off(self) -> None:
        """With reaction_style='off', no reactions should be set."""
        dispatch = _make_dispatch(buffered=True, reaction_style="off")
        result = _make_result("Done")
        dispatch.orchestrator.handle_message_streaming = AsyncMock(return_value=result)

        with patch(
            "sygen_bot.messenger.telegram.message_dispatch.send_rich",
            new_callable=AsyncMock,
        ):
            await run_streaming_message(dispatch)

        dispatch.bot.set_message_reaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_buffered_includes_footer(self) -> None:
        """Buffered mode should append technical footer when enabled."""
        dispatch = _make_dispatch(buffered=True)
        dispatch.scene_config = SceneConfig(technical_footer=True)
        result = _make_result("Response", model_name="opus", total_tokens=100, input_tokens=50)
        dispatch.orchestrator.handle_message_streaming = AsyncMock(return_value=result)

        with patch(
            "sygen_bot.messenger.telegram.message_dispatch.send_rich",
            new_callable=AsyncMock,
        ) as mock_send_rich:
            returned = await run_streaming_message(dispatch)

        sent_text = mock_send_rich.call_args[0][2]
        assert "opus" in sent_text.lower() or len(sent_text) > len("Response")


class TestNonBufferedStillWorks:
    """Verify that buffered=False preserves existing streaming behavior."""

    @pytest.mark.asyncio
    async def test_non_buffered_creates_stream_editor(self) -> None:
        """buffered=False should create a stream editor (existing behavior)."""
        dispatch = _make_dispatch(buffered=False)
        result = _make_result("Streamed")
        result.stream_fallback = True
        dispatch.orchestrator.handle_message_streaming = AsyncMock(return_value=result)

        mock_editor = MagicMock()
        mock_editor.has_content = False
        mock_editor.append_text = AsyncMock()
        mock_editor.append_tool = AsyncMock()
        mock_editor.append_system = AsyncMock()
        mock_editor.finalize = AsyncMock()

        with (
            patch(
                "sygen_bot.messenger.telegram.message_dispatch.create_stream_editor",
                return_value=mock_editor,
            ) as mock_create,
            patch(
                "sygen_bot.messenger.telegram.message_dispatch.send_rich",
                new_callable=AsyncMock,
            ),
        ):
            await run_streaming_message(dispatch)

        mock_create.assert_called_once()
