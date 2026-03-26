"""Tests for ToolRouter: config generation, CLI params, tool dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sygen_bot.config import MCPConfig, MCPServerConfig
from sygen_bot.mcp.client import MCPToolInfo
from sygen_bot.mcp.manager import MCPManager
from sygen_bot.mcp.tool_router import ToolRouter


def _make_router(tools: list[MCPToolInfo], servers: list[MCPServerConfig] | None = None, tmp_path: Path | None = None) -> ToolRouter:
    config = MCPConfig(enabled=True, servers=servers or [])
    manager = MagicMock(spec=MCPManager)
    manager.get_all_tools.return_value = tools
    manager._config = config
    manager.call_tool = AsyncMock(return_value="mocked_result")
    manager.server_status.return_value = {}
    workspace = tmp_path or Path("/tmp/test-workspace")
    return ToolRouter(manager, workspace)


class TestGenerateMCPConfigFile:
    def test_generates_valid_json(self, tmp_path):
        servers = [
            MCPServerConfig(name="fs", command="npx", args=["-y", "fs-server", "/tmp"]),
        ]
        tools = [MCPToolInfo(name="read", server_name="fs", description="Read file")]
        router = _make_router(tools, servers, tmp_path)

        config_path = router.generate_mcp_config_file()
        assert config_path.exists()

        data = json.loads(config_path.read_text())
        assert "mcpServers" in data
        assert "fs" in data["mcpServers"]
        assert data["mcpServers"]["fs"]["command"] == "npx"
        assert data["mcpServers"]["fs"]["args"] == ["-y", "fs-server", "/tmp"]

    def test_sse_server_format(self, tmp_path):
        servers = [
            MCPServerConfig(name="remote", transport="sse", url="http://localhost:3001/sse"),
        ]
        tools = [MCPToolInfo(name="query", server_name="remote")]
        router = _make_router(tools, servers, tmp_path)

        config_path = router.generate_mcp_config_file()
        data = json.loads(config_path.read_text())
        assert data["mcpServers"]["remote"]["url"] == "http://localhost:3001/sse"
        assert data["mcpServers"]["remote"]["type"] == "sse"

    def test_env_included(self, tmp_path):
        servers = [
            MCPServerConfig(name="s", command="cmd", env={"API_KEY": "secret"}),
        ]
        tools = [MCPToolInfo(name="t", server_name="s")]
        router = _make_router(tools, servers, tmp_path)

        config_path = router.generate_mcp_config_file()
        data = json.loads(config_path.read_text())
        assert data["mcpServers"]["s"]["env"]["API_KEY"] == "secret"

    def test_disabled_servers_excluded(self, tmp_path):
        servers = [
            MCPServerConfig(name="active", command="cmd", enabled=True),
            MCPServerConfig(name="disabled", command="cmd", enabled=False),
        ]
        tools = [MCPToolInfo(name="t", server_name="active")]
        router = _make_router(tools, servers, tmp_path)

        config_path = router.generate_mcp_config_file()
        data = json.loads(config_path.read_text())
        assert "active" in data["mcpServers"]
        assert "disabled" not in data["mcpServers"]


class TestGetCLIParameters:
    def test_returns_mcp_config_for_claude(self, tmp_path):
        servers = [MCPServerConfig(name="s", command="cmd")]
        tools = [MCPToolInfo(name="t", server_name="s")]
        router = _make_router(tools, servers, tmp_path)

        params = router.get_cli_parameters("claude")
        assert "--mcp-config" in params
        assert len(params) == 2

    def test_returns_empty_for_codex(self, tmp_path):
        tools = [MCPToolInfo(name="t", server_name="s")]
        router = _make_router(tools, tmp_path=tmp_path)
        assert router.get_cli_parameters("codex") == []

    def test_returns_empty_for_gemini(self, tmp_path):
        tools = [MCPToolInfo(name="t", server_name="s")]
        router = _make_router(tools, tmp_path=tmp_path)
        assert router.get_cli_parameters("gemini") == []

    def test_returns_empty_when_no_tools(self, tmp_path):
        router = _make_router([], tmp_path=tmp_path)
        assert router.get_cli_parameters("claude") == []


class TestGetToolDescriptions:
    def test_format(self):
        tools = [
            MCPToolInfo(name="read", server_name="fs", description="Read a file"),
            MCPToolInfo(name="write", server_name="fs", description="Write a file"),
        ]
        router = _make_router(tools)
        desc = router.get_tool_descriptions_for_prompt()
        assert "Available MCP tools:" in desc
        assert "fs/read: Read a file" in desc
        assert "fs/write: Write a file" in desc

    def test_empty_when_no_tools(self):
        router = _make_router([])
        assert router.get_tool_descriptions_for_prompt() == ""


class TestHandleToolCall:
    async def test_dispatches_to_correct_server(self, tmp_path):
        tools = [
            MCPToolInfo(name="read", server_name="fs"),
            MCPToolInfo(name="query", server_name="db"),
        ]
        router = _make_router(tools, tmp_path=tmp_path)

        result = await router.handle_tool_call("read", {"path": "/tmp"})
        router._manager.call_tool.assert_awaited_once_with("fs", "read", {"path": "/tmp"})
        assert result == "mocked_result"

    async def test_raises_for_unknown_tool(self, tmp_path):
        router = _make_router([], tmp_path=tmp_path)
        with pytest.raises(ValueError, match="not found"):
            await router.handle_tool_call("nonexistent")
