"""Integration tests: routing in the orchestrator flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sygen_bot.cli.types import AgentResponse
from sygen_bot.config import AgentConfig, RoutingConfig
from sygen_bot.orchestrator.core import Orchestrator
from sygen_bot.orchestrator.flows import normal
from sygen_bot.routing.router import ModelRouter
from sygen_bot.session.key import SessionKey
from sygen_bot.workspace.init import init_workspace
from sygen_bot.workspace.paths import SygenPaths


def _mock_response(**kwargs: object) -> AgentResponse:
    defaults: dict[str, object] = {
        "result": "ok",
        "session_id": "sess-1",
        "is_error": False,
        "cost_usd": 0.01,
        "total_tokens": 100,
    }
    defaults.update(kwargs)
    return AgentResponse(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def routing_orch(workspace) -> Orchestrator:
    """Orchestrator with routing enabled and mocked CLI + classifier."""
    paths, _config = workspace
    config = AgentConfig(
        routing=RoutingConfig(
            enabled=True,
            api_key="test-key",
            classifier_provider="anthropic",
            classifier_model="claude-haiku-4-5-20251001",
        ),
    )
    o = Orchestrator(config, paths)
    # Mock CLI
    mock_cli = MagicMock()
    mock_cli.execute = AsyncMock(return_value=_mock_response())
    mock_cli.execute_streaming = AsyncMock(return_value=_mock_response())
    object.__setattr__(o, "_cli_service", mock_cli)
    return o


async def test_routing_overrides_default_model(routing_orch: Orchestrator) -> None:
    """When routing is active and no @model directive, routing picks the model."""
    assert routing_orch._model_router is not None
    # Mock classifier to return "light"
    routing_orch._model_router._classifier.classify = AsyncMock(return_value="light")  # type: ignore[method-assign]

    await normal(routing_orch, SessionKey(chat_id=1), "hello")

    call_args = routing_orch._cli_service.execute.call_args
    request = call_args[0][0]
    assert request.model_override == "haiku"


async def test_routing_heavy_uses_opus(routing_orch: Orchestrator) -> None:
    """Heavy classification routes to opus."""
    assert routing_orch._model_router is not None
    routing_orch._model_router._classifier.classify = AsyncMock(return_value="heavy")  # type: ignore[method-assign]

    await normal(routing_orch, SessionKey(chat_id=1), "refactor auth")

    call_args = routing_orch._cli_service.execute.call_args
    request = call_args[0][0]
    assert request.model_override == "opus"


async def test_directive_overrides_routing(routing_orch: Orchestrator) -> None:
    """@sonnet directive takes priority over routing."""
    assert routing_orch._model_router is not None
    # Classifier says light (would pick haiku), but user said @sonnet
    routing_orch._model_router._classifier.classify = AsyncMock(return_value="light")  # type: ignore[method-assign]

    await normal(routing_orch, SessionKey(chat_id=1), "hello", model_override="sonnet")

    call_args = routing_orch._cli_service.execute.call_args
    request = call_args[0][0]
    assert request.model_override == "sonnet"


async def test_routing_disabled_uses_default(workspace) -> None:
    """When routing is disabled, default model is used."""
    paths, _config = workspace
    config = AgentConfig(model="sonnet")
    o = Orchestrator(config, paths)
    assert o._model_router is None

    mock_cli = MagicMock()
    mock_cli.execute = AsyncMock(return_value=_mock_response())
    object.__setattr__(o, "_cli_service", mock_cli)

    await normal(o, SessionKey(chat_id=1), "hello")

    call_args = mock_cli.execute.call_args
    request = call_args[0][0]
    assert request.model_override == "sonnet"


async def test_routing_no_api_key_skipped(workspace) -> None:
    """When routing enabled but no api_key, router is not created."""
    paths, _config = workspace
    config = AgentConfig(
        routing=RoutingConfig(enabled=True, api_key=""),
    )
    o = Orchestrator(config, paths)
    assert o._model_router is None


async def test_hot_reload_rebuilds_router(routing_orch: Orchestrator) -> None:
    """Hot-reload of routing config recreates the router."""
    old_router = routing_orch._model_router
    assert old_router is not None
    # Mock close so it doesn't fail
    old_router._classifier.close = AsyncMock()  # type: ignore[method-assign]

    # Simulate disabling routing
    routing_orch._config.routing = RoutingConfig(enabled=False)
    routing_orch._rebuild_model_router()

    assert routing_orch._model_router is None

    # Re-enable
    routing_orch._config.routing = RoutingConfig(enabled=True, api_key="new-key")
    routing_orch._rebuild_model_router()

    assert routing_orch._model_router is not None
