"""Tests for /mcp command handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sygen_bot.mcp.client import MCPToolInfo
from sygen_bot.mcp.commands import cmd_mcp
from sygen_bot.mcp.manager import MCPManager, ServerHealth
from sygen_bot.session import SessionKey


def _make_orch(*, mcp_enabled: bool = True, tools: list[MCPToolInfo] | None = None, health: dict[str, ServerHealth] | None = None):
    """Create a minimal mock Orchestrator with MCP state."""
    orch = MagicMock()

    if not mcp_enabled:
        orch._mcp_manager = None
        return orch

    manager = MagicMock(spec=MCPManager)
    manager.get_all_tools.return_value = tools or []
    manager.server_status.return_value = health or {}
    manager.refresh_tools = AsyncMock(return_value=tools or [])
    orch._mcp_manager = manager
    return orch


def _key():
    return SessionKey(chat_id=123)


class TestCmdMcpDisabled:
    async def test_mcp_not_enabled(self):
        orch = _make_orch(mcp_enabled=False)
        result = await cmd_mcp(orch, _key(), "/mcp")
        assert "not enabled" in result.text.lower()


class TestCmdMcpList:
    async def test_list_no_servers(self):
        orch = _make_orch()
        result = await cmd_mcp(orch, _key(), "/mcp")
        assert "No servers" in result.text

    async def test_list_with_servers(self):
        tools = [
            MCPToolInfo(name="read", server_name="fs", description="Read"),
            MCPToolInfo(name="write", server_name="fs", description="Write"),
        ]
        health = {
            "fs": ServerHealth(name="fs", connected=True),
        }
        orch = _make_orch(tools=tools, health=health)
        result = await cmd_mcp(orch, _key(), "/mcp")
        assert "fs" in result.text
        assert "read" in result.text
        assert "2 tools" in result.text


class TestCmdMcpStatus:
    async def test_status_no_servers(self):
        orch = _make_orch()
        result = await cmd_mcp(orch, _key(), "/mcp status")
        assert "No servers" in result.text

    async def test_status_with_health(self):
        health = {
            "srv": ServerHealth(name="srv", connected=True, restart_count=2),
        }
        orch = _make_orch(health=health)
        result = await cmd_mcp(orch, _key(), "/mcp status")
        assert "srv" in result.text
        assert "connected" in result.text
        assert "restarts: 2" in result.text

    async def test_status_disconnected_with_error(self):
        health = {
            "bad": ServerHealth(name="bad", connected=False, last_error="Connection refused"),
        }
        orch = _make_orch(health=health)
        result = await cmd_mcp(orch, _key(), "/mcp status")
        assert "disconnected" in result.text
        assert "Connection refused" in result.text


class TestCmdMcpRefresh:
    async def test_refresh(self):
        tools = [MCPToolInfo(name="t1", server_name="s1")]
        health = {"s1": ServerHealth(name="s1", connected=True)}
        orch = _make_orch(tools=tools, health=health)
        result = await cmd_mcp(orch, _key(), "/mcp refresh")
        assert "Refreshed" in result.text
        assert "1 tool" in result.text


class TestCmdMcpHelp:
    async def test_help(self):
        orch = _make_orch()
        result = await cmd_mcp(orch, _key(), "/mcp help")
        assert "/mcp" in result.text
        assert "status" in result.text
        assert "refresh" in result.text
