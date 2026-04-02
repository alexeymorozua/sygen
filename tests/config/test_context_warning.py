"""Tests for context window warning logic."""

from __future__ import annotations

from sygen_bot.orchestrator.flows import _context_warning
from sygen_bot.session import SessionData


def _make_session(
    provider: str = "claude",
    model: str = "opus",
    total_tokens: int = 0,
    context_warned: bool = False,
) -> SessionData:
    """Create a minimal session for testing."""
    s = SessionData(chat_id=123, provider=provider, model=model)
    s.total_tokens = total_tokens
    pd = s.provider_sessions.get(provider)
    if pd:
        pd.context_warned = context_warned
    return s


def test_no_warning_below_threshold() -> None:
    session = _make_session(total_tokens=800_000)
    result = _context_warning(session, 0, 90)
    assert result == ""


def test_warning_at_threshold() -> None:
    session = _make_session(total_tokens=900_001)
    result = _context_warning(session, 0, 90)
    assert "⚠️" in result
    assert "/new" in result
    assert "90%" in result or "91%" in result


def test_warning_shows_once() -> None:
    session = _make_session(total_tokens=950_000)
    result1 = _context_warning(session, 0, 90)
    assert "⚠️" in result1

    result2 = _context_warning(session, 0, 90)
    assert result2 == ""


def test_already_warned_no_repeat() -> None:
    session = _make_session(total_tokens=950_000, context_warned=True)
    result = _context_warning(session, 0, 90)
    assert result == ""


def test_override_context_window() -> None:
    session = _make_session(total_tokens=180_000)
    # With 200K override, 90% = 180K → should trigger
    result = _context_warning(session, 200_000, 90)
    assert "⚠️" in result
    assert "90%" in result


def test_codex_auto_detect_200k() -> None:
    session = _make_session(provider="codex", model="gpt-5.2-codex", total_tokens=190_000)
    result = _context_warning(session, 0, 90)
    assert "⚠️" in result


def test_codex_below_threshold() -> None:
    session = _make_session(provider="codex", model="gpt-5.2-codex", total_tokens=100_000)
    result = _context_warning(session, 0, 90)
    assert result == ""


def test_disabled_with_zero_percent() -> None:
    session = _make_session(total_tokens=999_999)
    result = _context_warning(session, 0, 0)
    assert result == ""


def test_none_session() -> None:
    result = _context_warning(None, 0, 90)
    assert result == ""
