"""Tests for MessageClassifier."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from sygen_bot.config import RoutingConfig
from sygen_bot.routing.classifier import MessageClassifier


def _make_config(**overrides: object) -> RoutingConfig:
    defaults: dict[str, object] = {
        "enabled": True,
        "api_key": "test-key",
        "classifier_provider": "anthropic",
        "classifier_model": "claude-haiku-4-5-20251001",
    }
    defaults.update(overrides)
    return RoutingConfig(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def classifier() -> MessageClassifier:
    return MessageClassifier(_make_config())


# -- Anthropic provider --


async def test_classify_anthropic_light(classifier: MessageClassifier) -> None:
    mock_response = httpx.Response(
        200,
        json={"content": [{"text": "1"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    with patch.object(classifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("hello")
    assert result == "light"


async def test_classify_anthropic_medium(classifier: MessageClassifier) -> None:
    mock_response = httpx.Response(
        200,
        json={"content": [{"text": "2"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    with patch.object(classifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("explain how async works")
    assert result == "medium"


async def test_classify_anthropic_heavy(classifier: MessageClassifier) -> None:
    mock_response = httpx.Response(
        200,
        json={"content": [{"text": "3"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    with patch.object(classifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("refactor the entire auth module")
    assert result == "heavy"


# -- OpenAI provider --


async def test_classify_openai() -> None:
    config = _make_config(classifier_provider="openai", classifier_model="gpt-4o-mini")
    c = MessageClassifier(config)
    mock_response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "1"}}]},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    with patch.object(c._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await c.classify("hi")
    assert result == "light"
    await c.close()


# -- Google provider --


async def test_classify_google() -> None:
    config = _make_config(classifier_provider="google", classifier_model="gemini-2.0-flash")
    c = MessageClassifier(config)
    mock_response = httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": "3"}]}}]},
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"),
    )
    with patch.object(c._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await c.classify("design a microservice architecture")
    assert result == "heavy"
    await c.close()


# -- Fallback on errors --


async def test_classify_timeout_returns_medium(classifier: MessageClassifier) -> None:
    with patch.object(
        classifier._client, "post", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timeout")
    ):
        result = await classifier.classify("anything")
    assert result == "medium"


async def test_classify_http_error_returns_medium(classifier: MessageClassifier) -> None:
    error_response = httpx.Response(
        500,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    with patch.object(
        classifier._client, "post", new_callable=AsyncMock, side_effect=httpx.HTTPStatusError("fail", request=error_response.request, response=error_response)
    ):
        result = await classifier.classify("anything")
    assert result == "medium"


async def test_classify_unknown_provider_returns_medium() -> None:
    config = _make_config(classifier_provider="unknown")
    c = MessageClassifier(config)
    result = await c.classify("hello")
    assert result == "medium"
    await c.close()


# -- Parse edge cases --


async def test_classify_strips_whitespace(classifier: MessageClassifier) -> None:
    mock_response = httpx.Response(
        200,
        json={"content": [{"text": " 3\n"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    with patch.object(classifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("test")
    assert result == "heavy"


async def test_classify_unexpected_value_returns_medium(classifier: MessageClassifier) -> None:
    mock_response = httpx.Response(
        200,
        json={"content": [{"text": "5"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    with patch.object(classifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("test")
    assert result == "medium"


async def test_close(classifier: MessageClassifier) -> None:
    with patch.object(classifier._client, "aclose", new_callable=AsyncMock) as mock_close:
        await classifier.close()
    mock_close.assert_awaited_once()
