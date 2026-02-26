"""Abort trigger detection for the Telegram bot.

Recognises the ``/stop`` command and bare-word abort triggers in
English and German.
"""

from __future__ import annotations

ABORT_WORDS: frozenset[str] = frozenset(
    {
        # English
        "stop",
        "abort",
        "cancel",
        "halt",
        "hold",
        "wait",
        "quit",
        "exit",
        "esc",
        "interrupt",
        # German
        "stopp",
        "warte",
        "abbruch",
        "abbrechen",
        "aufhören",
    }
)


def is_abort_trigger(text: str) -> bool:
    """Return *True* if *text* is a single bare-word abort trigger."""
    stripped = text.strip().lower()
    if " " in stripped:
        return False
    return stripped in ABORT_WORDS


def is_abort_message(text: str) -> bool:
    """Return *True* if *text* is a ``/stop`` command or a bare-word abort."""
    stripped = text.strip()
    command = stripped.lower().split(None, 1)[0] if stripped else ""
    if command == "/stop" or command.startswith("/stop@"):
        return True
    return is_abort_trigger(stripped)
