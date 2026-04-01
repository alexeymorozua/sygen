"""Tests for CLI response parsing -- the critical output->CLIResponse conversion."""

from __future__ import annotations

import json
from typing import Any

from sygen_bot.cli.claude_provider import _parse_response
from sygen_bot.cli.codex_events import parse_codex_jsonl

# -- Claude _parse_response --


def test_parse_empty_stdout() -> None:
    resp = _parse_response(b"", b"", 0)
    assert resp.is_error is True
    assert resp.result == ""


def test_parse_valid_json_response() -> None:
    data = {
        "session_id": "sess-abc",
        "result": "Hello world!",
        "is_error": False,
        "duration_ms": 1500.0,
        "duration_api_ms": 1200.0,
        "total_cost_usd": 0.05,
        "num_turns": 3,
        "usage": {"input_tokens": 500, "output_tokens": 200},
        "modelUsage": {"claude-opus-4-20250514": {"input_tokens": 500}},
    }
    resp = _parse_response(json.dumps(data).encode(), b"", 0)
    assert resp.is_error is False
    assert resp.result == "Hello world!"
    assert resp.session_id == "sess-abc"
    assert resp.total_cost_usd == 0.05
    assert resp.num_turns == 3
    assert resp.input_tokens == 500
    assert resp.output_tokens == 200
    assert resp.total_tokens == 700
    assert resp.duration_ms == 1500.0
    assert resp.model_usage["claude-opus-4-20250514"]["input_tokens"] == 500


def test_parse_error_response() -> None:
    data = {"result": "Rate limit exceeded", "is_error": True}
    resp = _parse_response(json.dumps(data).encode(), b"", 1)
    assert resp.is_error is True
    assert resp.result == "Rate limit exceeded"


def test_parse_invalid_json_stdout() -> None:
    resp = _parse_response(b"This is not JSON at all", b"", 1)
    assert resp.is_error is True
    assert "This is not JSON" in resp.result


def test_parse_stderr_captured() -> None:
    data = {"result": "OK", "is_error": False}
    resp = _parse_response(json.dumps(data).encode(), b"some warning text", 0)
    assert resp.is_error is False
    assert resp.result == "OK"


def test_parse_missing_fields_use_defaults() -> None:
    data: dict[str, Any] = {}
    resp = _parse_response(json.dumps(data).encode(), b"", 0)
    assert resp.result == ""
    assert resp.is_error is False
    assert resp.session_id is None
    assert resp.total_cost_usd is None


def test_parse_returncode_captured() -> None:
    data = {"result": "done", "is_error": False}
    resp = _parse_response(json.dumps(data).encode(), b"", 42)
    assert resp.returncode == 42


def test_parse_json_array_from_mcp() -> None:
    """Claude CLI with MCP returns a JSON array; last dict entry should be used."""
    mcp_meta = {"type": "mcp_tool_call", "tool": "jira_search"}
    result_obj = {
        "session_id": "sess-mcp",
        "result": "Found 3 issues",
        "is_error": False,
        "num_turns": 2,
    }
    raw = json.dumps([mcp_meta, result_obj]).encode()
    resp = _parse_response(raw, b"", 0)
    assert resp.is_error is False
    assert resp.result == "Found 3 issues"
    assert resp.session_id == "sess-mcp"
    assert resp.num_turns == 2


def test_parse_json_array_empty_list() -> None:
    """Empty JSON array should produce a safe error-free empty response."""
    raw = json.dumps([]).encode()
    resp = _parse_response(raw, b"", 0)
    assert resp.result == ""


def test_parse_json_array_prefers_type_result() -> None:
    """When array has multiple dicts, prefer the one with type=='result'."""
    init_event = {"type": "system", "subtype": "init", "session_id": "wrong"}
    result_event = {
        "type": "result",
        "session_id": "abc123",
        "result": "Hello",
        "is_error": False,
        "num_turns": 1,
    }
    trailing_event = {"type": "tool_use", "name": "Read"}
    raw = json.dumps([init_event, result_event, trailing_event]).encode()
    resp = _parse_response(raw, b"", 0)
    assert resp.session_id == "abc123"
    assert resp.result == "Hello"
    assert resp.is_error is False


def test_parse_json_array_single_result() -> None:
    """Claude CLI 2.1.89+ with --output-format json --resume returns [result]."""
    raw = json.dumps([{
        "type": "result",
        "session_id": "abc123",
        "result": "Hello",
        "is_error": False,
    }]).encode()
    resp = _parse_response(raw, b"", 0)
    assert resp.session_id == "abc123"
    assert resp.result == "Hello"


def test_parse_json_array_no_dicts() -> None:
    """JSON array with no dict entries falls back to empty dict."""
    raw = json.dumps(["string", 42, True]).encode()
    resp = _parse_response(raw, b"", 0)
    assert resp.result == ""


# -- Codex parse_codex_jsonl --


def test_codex_parse_legacy_message_format() -> None:
    """The message/assistant/content[] format used by openclaw-compat."""
    line = json.dumps(
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Legacy output"}],
        }
    )
    text, _, _ = parse_codex_jsonl(line)
    assert text == "Legacy output"


def test_codex_parse_fallback_item_text() -> None:
    """Top-level item.text with empty type should be extracted."""
    line = json.dumps({"item": {"type": "", "text": "Fallback text"}})
    text, _, _ = parse_codex_jsonl(line)
    assert text == "Fallback text"


def test_codex_parse_thread_id_fallback() -> None:
    """thread_id at top level (not in thread.started event)."""
    line = json.dumps({"thread_id": "fallback-tid"})
    _, tid, _ = parse_codex_jsonl(line)
    assert tid == "fallback-tid"


def test_codex_parse_usage_fallback() -> None:
    """usage at top level (not in turn.completed event)."""
    line = json.dumps({"usage": {"total_tokens": 999}})
    _, _, usage = parse_codex_jsonl(line)
    assert usage is not None
    assert usage["total_tokens"] == 999
