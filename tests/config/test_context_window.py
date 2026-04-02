"""Tests for context window auto-detection."""

from sygen_bot.config import get_context_window


def test_claude_models_have_1m_context() -> None:
    for model in ("haiku", "sonnet", "opus"):
        assert get_context_window("claude", model) == 1_000_000


def test_gemini_2_5_models_have_1m_context() -> None:
    for model in ("gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"):
        assert get_context_window("gemini", model) == 1_000_000


def test_gemini_3_pro_has_2m_context() -> None:
    assert get_context_window("gemini", "gemini-3-pro-preview") == 2_000_000
    assert get_context_window("gemini", "gemini-3.1-pro-preview") == 2_000_000


def test_codex_models_have_200k_context() -> None:
    for model in ("gpt-5.2-codex", "gpt-5.3-codex", "gpt-5.1-codex-mini", "o4-mini"):
        assert get_context_window("codex", model) == 200_000


def test_unknown_model_falls_back_to_provider_default() -> None:
    assert get_context_window("claude", "future-model") == 1_000_000
    assert get_context_window("codex", "future-model") == 200_000
    assert get_context_window("gemini", "future-model") == 1_000_000


def test_unknown_provider_falls_back_to_1m() -> None:
    assert get_context_window("unknown", "whatever") == 1_000_000
