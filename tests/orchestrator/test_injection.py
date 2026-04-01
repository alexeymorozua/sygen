"""Tests for orchestrator/injection.py: _inject_prompt model override handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sygen_bot.cli.types import AgentResponse
from sygen_bot.config import AgentConfig
from sygen_bot.orchestrator.core import Orchestrator
from sygen_bot.orchestrator.injection import _inject_prompt
from sygen_bot.session import SessionData
from sygen_bot.workspace.paths import SygenPaths


@pytest.fixture
def orch_inject(workspace: tuple[SygenPaths, AgentConfig]) -> Orchestrator:
    """Orchestrator with mocked CLIService and sessions for injection tests."""
    paths, config = workspace
    config.allowed_user_ids = [100]
    o = Orchestrator(config, paths)
    mock_cli = MagicMock()
    mock_cli.execute = AsyncMock(
        return_value=AgentResponse(result="ok", session_id="s1")
    )
    object.__setattr__(o, "_cli_service", mock_cli)
    return o


class TestInjectPromptModelOverride:
    async def test_inject_prompt_passes_model_override(
        self, orch_inject: Orchestrator
    ) -> None:
        """When active session has model='opus', AgentRequest gets model_override='opus'."""
        sd = SessionData(100, session_id="sess-x")
        sd.model = "opus"
        sd.provider = "claude"
        orch_inject._sessions.get_active = AsyncMock(return_value=sd)
        orch_inject._sessions.update_session = AsyncMock()

        await _inject_prompt(orch_inject, "hello", 100, "test")

        request = orch_inject._cli_service.execute.call_args[0][0]
        assert request.model_override == "opus"
        assert request.provider_override == "claude"

    async def test_inject_prompt_no_override_without_session(
        self, orch_inject: Orchestrator
    ) -> None:
        """Without active session, overrides are None."""
        orch_inject._sessions.get_active = AsyncMock(return_value=None)

        await _inject_prompt(orch_inject, "hello", 100, "test")

        request = orch_inject._cli_service.execute.call_args[0][0]
        assert request.model_override is None
        assert request.provider_override is None
