"""Tests for is_meta_only() — short parenthetical meta-message detection."""

from __future__ import annotations

import pytest

from sygen_bot.text.response_format import is_meta_only


@pytest.mark.parametrize(
    "text",
    [
        "(уже обработано — транскрипция была прочитана и ответ отправлен)",
        "(already processed — transcription was read and response sent)",
        "(done)",
        "  (some meta note)  ",
    ],
)
def test_detects_meta_messages(text: str) -> None:
    assert is_meta_only(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "This is a normal response.",
        "(parenthetical) followed by more text",
        "Some text (with parenthetical) inside",
        "(short)\n(two lines)",
        "",
        "   ",
        "A" * 201,
        "(A" + "x" * 200 + ")",
        "Вот ответ на твой вопрос:\n\n(пояснение в скобках)",
    ],
)
def test_rejects_normal_text(text: str) -> None:
    assert is_meta_only(text) is False
