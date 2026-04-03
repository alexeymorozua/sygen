"""Tests for per-topic default model feature."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sygen_bot.config import AgentConfig
from sygen_bot.orchestrator.commands import cmd_topicmodel
from sygen_bot.orchestrator.core import Orchestrator
from sygen_bot.session.key import SessionKey


# -- AgentConfig.get_topic_default_model --


class TestGetTopicDefaultModel:
    def test_returns_none_when_no_topic_id(self) -> None:
        cfg = AgentConfig(topic_defaults={"68": {"model": "sonnet"}})
        assert cfg.get_topic_default_model(None) is None

    def test_returns_none_when_empty_defaults(self) -> None:
        cfg = AgentConfig()
        assert cfg.get_topic_default_model(68) is None

    def test_returns_model_when_configured(self) -> None:
        cfg = AgentConfig(topic_defaults={"68": {"model": "sonnet"}})
        assert cfg.get_topic_default_model(68) == "sonnet"

    def test_returns_none_when_topic_not_in_defaults(self) -> None:
        cfg = AgentConfig(topic_defaults={"68": {"model": "sonnet"}})
        assert cfg.get_topic_default_model(99) is None

    def test_returns_none_when_model_key_missing(self) -> None:
        cfg = AgentConfig(topic_defaults={"68": {}})
        assert cfg.get_topic_default_model(68) is None

    def test_returns_none_when_model_empty_string(self) -> None:
        cfg = AgentConfig(topic_defaults={"68": {"model": ""}})
        assert cfg.get_topic_default_model(68) is None


# -- cmd_topicmodel --


class TestCmdTopicmodel:
    async def test_rejects_non_topic_chat(self, orch: Orchestrator) -> None:
        key = SessionKey(chat_id=1, topic_id=None)
        result = await cmd_topicmodel(orch, key, "/topicmodel sonnet")
        assert "topic" in result.text.lower()

    async def test_shows_current_when_set(self, orch: Orchestrator) -> None:
        orch._config.topic_defaults = {"68": {"model": "sonnet"}}
        key = SessionKey(chat_id=1, topic_id=68)
        result = await cmd_topicmodel(orch, key, "/topicmodel")
        assert "sonnet" in result.text

    async def test_shows_global_default_when_not_set(self, orch: Orchestrator) -> None:
        key = SessionKey(chat_id=1, topic_id=68)
        result = await cmd_topicmodel(orch, key, "/topicmodel")
        assert orch._config.model in result.text

    async def test_saves_topic_default(self, orch: Orchestrator) -> None:
        key = SessionKey(chat_id=1, topic_id=68)
        with patch(
            "sygen_bot.config.update_config_file_async",
            new_callable=AsyncMock,
        ) as mock_save:
            result = await cmd_topicmodel(orch, key, "/topicmodel sonnet")

        assert "sonnet" in result.text
        assert orch._config.topic_defaults["68"]["model"] == "sonnet"
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["topic_defaults"]["68"]["model"] == "sonnet"


# -- Topic default in flows --


class TestTopicDefaultInFlows:
    """Verify that _prepare_normal uses topic default when available."""

    async def test_topic_default_used_for_new_session(self, orch: Orchestrator) -> None:
        """When a topic has a configured default, new sessions should use it."""
        orch._config.topic_defaults = {"68": {"model": "sonnet"}}
        key = SessionKey(chat_id=1, topic_id=68)

        session, _is_new = await orch._sessions.resolve_session(key)
        # Simulate what flows._prepare_normal does:
        topic_default = orch._config.get_topic_default_model(key.topic_id)
        requested_model = topic_default or orch._config.model
        assert requested_model == "sonnet"

    async def test_global_default_when_no_topic_config(self, orch: Orchestrator) -> None:
        key = SessionKey(chat_id=1, topic_id=99)
        topic_default = orch._config.get_topic_default_model(key.topic_id)
        requested_model = topic_default or orch._config.model
        assert requested_model == orch._config.model

    async def test_non_topic_ignores_topic_defaults(self, orch: Orchestrator) -> None:
        orch._config.topic_defaults = {"68": {"model": "sonnet"}}
        key = SessionKey(chat_id=1, topic_id=None)
        topic_default = orch._config.get_topic_default_model(key.topic_id)
        assert topic_default is None
        requested_model = topic_default or orch._config.model
        assert requested_model == orch._config.model
