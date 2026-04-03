"""Tests for compact-count-based context warning logic."""

from __future__ import annotations

from sygen_bot.orchestrator.flows import _context_warning
from sygen_bot.session import SessionData


def _make_session(
    provider: str = "claude",
    model: str = "opus",
    compact_count: int = 0,
    context_warned: bool = False,
) -> SessionData:
    """Create a minimal session for testing."""
    s = SessionData(chat_id=123, provider=provider, model=model)
    s.compact_count = compact_count
    pd = s.provider_sessions.get(provider)
    if pd:
        pd.context_warned = context_warned
    return s


def test_no_warning_below_threshold() -> None:
    session = _make_session(compact_count=2)
    result = _context_warning(session, 3)
    assert result == ""


def test_warning_at_threshold() -> None:
    session = _make_session(compact_count=3)
    result = _context_warning(session, 3)
    assert "⚠️" in result
    assert "/new" in result


def test_warning_above_threshold() -> None:
    session = _make_session(compact_count=5)
    result = _context_warning(session, 3)
    assert "⚠️" in result


def test_warning_shows_once() -> None:
    session = _make_session(compact_count=3)
    result1 = _context_warning(session, 3)
    assert "⚠️" in result1

    result2 = _context_warning(session, 3)
    assert result2 == ""


def test_already_warned_no_repeat() -> None:
    session = _make_session(compact_count=5, context_warned=True)
    result = _context_warning(session, 3)
    assert result == ""


def test_disabled_with_zero_threshold() -> None:
    session = _make_session(compact_count=10)
    result = _context_warning(session, 0)
    assert result == ""


def test_none_session() -> None:
    result = _context_warning(None, 3)
    assert result == ""


def test_zero_compacts_no_warning() -> None:
    session = _make_session(compact_count=0)
    result = _context_warning(session, 3)
    assert result == ""


def test_threshold_of_one() -> None:
    session = _make_session(compact_count=1)
    result = _context_warning(session, 1)
    assert "⚠️" in result
