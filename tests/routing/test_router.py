"""Tests for ModelRouter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sygen_bot.config import RoutingConfig, RoutingTierConfig
from sygen_bot.routing.classifier import ClassificationResult, MessageClassifier
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


def _mock_classify(router: ModelRouter, tier: str, background: bool = False) -> None:
    """Mock classify_full on the router's classifier."""
    router._classifier.classify_full = AsyncMock(  # type: ignore[method-assign]
        return_value=ClassificationResult(tier=tier, background=background)
    )


# -- Tier-to-model mapping --


async def test_resolve_light_claude() -> None:
    router = _make_router()
    _mock_classify(router, "light")
    model = await router.resolve_model("hello", "claude")
    assert model == "haiku"


async def test_resolve_medium_claude() -> None:
    router = _make_router()
    _mock_classify(router, "medium")
    model = await router.resolve_model("explain this", "claude")
    assert model == "sonnet"


async def test_resolve_heavy_claude() -> None:
    router = _make_router()
    _mock_classify(router, "heavy")
    model = await router.resolve_model("refactor auth", "claude")
    assert model == "opus"


async def test_resolve_codex_tiers() -> None:
    router = _make_router()
    _mock_classify(router, "light")
    model = await router.resolve_model("hi", "codex")
    assert model == "gpt-4o-mini"


async def test_resolve_gemini_heavy() -> None:
    router = _make_router()
    _mock_classify(router, "heavy")
    model = await router.resolve_model("design architecture", "gemini")
    assert model == "pro"


# -- Disabled / missing config --


async def test_disabled_returns_none() -> None:
    config = _make_config(enabled=False, auto_delegate=False)
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
    _mock_classify(router, "light")
    result = await router.resolve_model("hello", "unknown_provider")
    assert result is None


async def test_empty_tier_model_returns_none() -> None:
    config = _make_config(
        tiers={"claude": RoutingTierConfig(light="", medium="sonnet", heavy="opus")}
    )
    router = _make_router(config)
    _mock_classify(router, "light")
    result = await router.resolve_model("hello", "claude")
    assert result is None


# -- Custom tiers --


async def test_custom_tier_config() -> None:
    config = _make_config(
        tiers={"claude": RoutingTierConfig(light="haiku", medium="haiku", heavy="sonnet")}
    )
    router = _make_router(config)
    _mock_classify(router, "heavy")
    model = await router.resolve_model("big task", "claude")
    assert model == "sonnet"


# -- Background delegation --


async def test_resolve_background_flag() -> None:
    config = _make_config(auto_delegate=True)
    router = _make_router(config)
    _mock_classify(router, "heavy", background=True)
    decision = await router.resolve("research task", "claude")
    assert decision.background is True
    assert decision.model == "opus"


async def test_resolve_no_background_when_disabled() -> None:
    config = _make_config(auto_delegate=False)
    router = _make_router(config)
    _mock_classify(router, "heavy", background=True)
    decision = await router.resolve("research task", "claude")
    assert decision.background is False
    assert decision.model == "opus"


async def test_resolve_model_only_no_routing() -> None:
    """auto_delegate on but routing disabled: model=None, bg works."""
    config = _make_config(enabled=False, auto_delegate=True)
    router = _make_router(config)
    _mock_classify(router, "heavy", background=True)
    decision = await router.resolve("research task", "claude")
    assert decision.model is None
    assert decision.background is True


# -- Close --


async def test_close_delegates_to_classifier() -> None:
    router = _make_router()
    router._classifier.close = AsyncMock()  # type: ignore[method-assign]
    await router.close()
    router._classifier.close.assert_awaited_once()
