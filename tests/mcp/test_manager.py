"""Tests for MCPManager lifecycle and health monitoring."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sygen_bot.config import MCPConfig, MCPServerConfig
from sygen_bot.mcp.client import MCPClient, MCPToolInfo
from sygen_bot.mcp.manager import MCPManager, ServerHealth


def _make_config(*servers: MCPServerConfig) -> MCPConfig:
    return MCPConfig(enabled=True, servers=list(servers))


def _server(name: str, enabled: bool = True) -> MCPServerConfig:
    return MCPServerConfig(name=name, command="echo", args=[name], enabled=enabled)


async def _fake_connect(self):
    """Mock connect that marks the client as connected."""
    self._connected = True


class TestMCPManager:
    async def test_start_stop_empty(self):
        mgr = MCPManager(_make_config())
        await mgr.start()
        assert mgr.get_all_tools() == []
        assert mgr.server_status() == {}
        await mgr.stop()

    @patch.object(MCPClient, "connect", new=_fake_connect)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[
        MCPToolInfo(name="tool_a", server_name="srv1"),
        MCPToolInfo(name="tool_b", server_name="srv1"),
    ])
    async def test_start_connects_enabled_servers(self, mock_list):
        cfg = _make_config(_server("srv1"), _server("srv2", enabled=False))
        mgr = MCPManager(cfg)
        await mgr.start()

        assert "srv1" in mgr.server_status()
        assert "srv2" not in mgr.server_status()

        tools = mgr.get_all_tools()
        assert len(tools) == 2

        await mgr.stop()

    @patch.object(MCPClient, "connect", new_callable=AsyncMock)
    @patch.object(MCPClient, "disconnect", new_callable=AsyncMock)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[])
    async def test_stop_disconnects_all(self, mock_list, mock_disconnect, mock_connect):
        cfg = _make_config(_server("a"), _server("b"))
        mgr = MCPManager(cfg)
        await mgr.start()
        await mgr.stop()

        assert mock_disconnect.call_count == 2
        assert mgr.server_status() == {}
        assert mgr.get_all_tools() == []

    @patch.object(MCPClient, "connect", new_callable=AsyncMock)
    @patch.object(MCPClient, "disconnect", new_callable=AsyncMock)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[])
    async def test_restart_server(self, mock_list, mock_disconnect, mock_connect):
        cfg = _make_config(_server("srv1"))
        mgr = MCPManager(cfg)
        await mgr.start()

        await mgr.restart_server("srv1")
        assert mock_disconnect.call_count >= 1
        # connect called at start + restart
        assert mock_connect.call_count >= 2

        await mgr.stop()

    @patch.object(MCPClient, "connect", new=_fake_connect)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[
        MCPToolInfo(name="new_tool", server_name="added"),
    ])
    async def test_add_server(self, mock_list):
        mgr = MCPManager(_make_config())
        await mgr.start()

        await mgr.add_server(_server("added"))
        assert "added" in mgr.server_status()
        assert len(mgr.get_all_tools()) == 1

        await mgr.stop()

    @patch.object(MCPClient, "connect", new_callable=AsyncMock)
    @patch.object(MCPClient, "disconnect", new_callable=AsyncMock)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[])
    async def test_remove_server(self, mock_list, mock_disconnect, mock_connect):
        cfg = _make_config(_server("srv1"))
        mgr = MCPManager(cfg)
        await mgr.start()

        await mgr.remove_server("srv1")
        assert "srv1" not in mgr.server_status()
        assert mock_disconnect.call_count >= 1

        await mgr.stop()

    @patch.object(MCPClient, "connect", new=_fake_connect)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[
        MCPToolInfo(name="t1", server_name="s1"),
    ])
    async def test_refresh_tools(self, mock_list):
        cfg = _make_config(_server("s1"))
        mgr = MCPManager(cfg)
        await mgr.start()

        # Simulate adding more tools
        mock_list.return_value = [
            MCPToolInfo(name="t1", server_name="s1"),
            MCPToolInfo(name="t2", server_name="s1"),
        ]
        tools = await mgr.refresh_tools()
        assert len(tools) == 2

        await mgr.stop()

    @patch.object(MCPClient, "connect", new_callable=AsyncMock)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[
        MCPToolInfo(name="t1", server_name="s1"),
    ])
    @patch.object(MCPClient, "call_tool", new_callable=AsyncMock, return_value="result123")
    async def test_call_tool(self, mock_call, mock_list, mock_connect):
        cfg = _make_config(_server("s1"))
        mgr = MCPManager(cfg)
        await mgr.start()

        # Mark as connected
        mgr._clients["s1"]._connected = True

        result = await mgr.call_tool("s1", "t1", {"arg": "val"})
        assert result == "result123"

        await mgr.stop()

    async def test_call_tool_not_connected(self):
        mgr = MCPManager(_make_config())
        await mgr.start()

        with pytest.raises(RuntimeError, match="not connected"):
            await mgr.call_tool("nonexistent", "t1")

        await mgr.stop()

    @patch.object(MCPClient, "connect", new_callable=AsyncMock)
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[])
    async def test_server_status(self, mock_list, mock_connect):
        cfg = _make_config(_server("s1"), _server("s2"))
        mgr = MCPManager(cfg)
        await mgr.start()

        status = mgr.server_status()
        assert "s1" in status
        assert "s2" in status
        assert isinstance(status["s1"], ServerHealth)

        await mgr.stop()

    @patch.object(MCPClient, "connect", new_callable=AsyncMock, side_effect=ConnectionError("fail"))
    @patch.object(MCPClient, "list_tools", new_callable=AsyncMock, return_value=[])
    async def test_connect_failure_recorded(self, mock_list, mock_connect):
        cfg = _make_config(_server("bad"))
        mgr = MCPManager(cfg)
        await mgr.start()

        status = mgr.server_status()
        assert "bad" in status
        assert status["bad"].connected is False
        assert "fail" in status["bad"].last_error

        await mgr.stop()

    async def test_restart_unknown_server(self):
        mgr = MCPManager(_make_config())
        await mgr.start()
        # Should not raise, just log
        await mgr.restart_server("ghost")
        await mgr.stop()
