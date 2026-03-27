"""Tests for ModelRouter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sygen_bot.config import RoutingConfig, RoutingTierConfig
from sygen_bot.routing.classifier import MessageClassifier
from sygen_bot.routing.router import ModelRouter


def _make_config(**overrides: object) -> RoutingConfig:
    defaults: dict[str, object] = {
        "enabled": True,
        "api_key": "test-key",
        "classifier_provider": "anthropic",
        "classifier_model": "claude-haiku-4-5-20251001",
    }
    defaults.update(overrides)
    return RoutingConfig(**defaults)  # type: ignore[arg-type]


def _make_router(config: RoutingConfig | None = None) -> ModelRouter:
    cfg = config or _make_config()
    classifier = MessageClassifier(cfg)
    return ModelRouter(cfg, classifier)


# -- Tier-to-model mapping --


async def test_resolve_light_claude() -> None:
    router = _make_router()
    router._classifier.classify = AsyncMock(return_value="light")  # type: ignore[method-assign]
    model = await router.resolve_model("hello", "claude")
    assert model == "haiku"


async def test_resolve_medium_claude() -> None:
    router = _make_router()
    router._classifier.classify = AsyncMock(return_value="medium")  # type: ignore[method-assign]
    model = await router.resolve_model("explain this", "claude")
    assert model == "sonnet"


async def test_resolve_heavy_claude() -> None:
    router = _make_router()
    router._classifier.classify = AsyncMock(return_value="heavy")  # type: ignore[method-assign]
    model = await router.resolve_model("refactor auth", "claude")
    assert model == "opus"


async def test_resolve_codex_tiers() -> None:
    router = _make_router()
    router._classifier.classify = AsyncMock(return_value="light")  # type: ignore[method-assign]
    model = await router.resolve_model("hi", "codex")
    assert model == "gpt-4o-mini"


async def test_resolve_gemini_heavy() -> None:
    router = _make_router()
    router._classifier.classify = AsyncMock(return_value="heavy")  # type: ignore[method-assign]
    model = await router.resolve_model("design architecture", "gemini")
    assert model == "pro"


# -- Disabled / missing config --


async def test_disabled_returns_none() -> None:
    config = _make_config(enabled=False)
    router = _make_router(config)
    result = await router.resolve_model("anything", "claude")
    assert result is None


async def test_no_api_key_returns_none() -> None:
    config = _make_config(api_key="")
    router = _make_router(config)
    result = await router.resolve_model("anything", "claude")
    assert result is None


async def test_unknown_provider_returns_none() -> None:
    router = _make_router()
    router._classifier.classify = AsyncMock(return_value="light")  # type: ignore[method-assign]
    result = await router.resolve_model("hello", "unknown_provider")
    assert result is None


async def test_empty_tier_model_returns_none() -> None:
    config = _make_config(
        tiers={"claude": RoutingTierConfig(light="", medium="sonnet", heavy="opus")}
    )
    router = _make_router(config)
    router._classifier.classify = AsyncMock(return_value="light")  # type: ignore[method-assign]
    result = await router.resolve_model("hello", "claude")
    assert result is None


# -- Custom tiers --


async def test_custom_tier_config() -> None:
    config = _make_config(
        tiers={"claude": RoutingTierConfig(light="haiku", medium="haiku", heavy="sonnet")}
    )
    router = _make_router(config)
    router._classifier.classify = AsyncMock(return_value="heavy")  # type: ignore[method-assign]
    model = await router.resolve_model("big task", "claude")
    assert model == "sonnet"


# -- Close --


async def test_close_delegates_to_classifier() -> None:
    router = _make_router()
    router._classifier.close = AsyncMock()  # type: ignore[method-assign]
    await router.close()
    router._classifier.close.assert_awaited_once()
