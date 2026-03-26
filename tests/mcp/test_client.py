"""Tests for MCPClient with mocked transports."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sygen_bot.config import MCPServerConfig
from sygen_bot.mcp.client import MCPClient, MCPToolInfo


@dataclass
class _FakeTool:
    name: str
    description: str = ""
    inputSchema: dict[str, Any] | None = None


@dataclass
class _FakeListResult:
    tools: list[_FakeTool]


@dataclass
class _FakeCallResult:
    content: str = "ok"


def _make_fake_session():
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=_FakeListResult(tools=[
        _FakeTool(name="read_file", description="Read a file", inputSchema={"type": "object"}),
        _FakeTool(name="write_file", description="Write a file"),
    ]))
    session.call_tool = AsyncMock(return_value=_FakeCallResult(content="tool result"))
    return session


@asynccontextmanager
async def _fake_stdio_client(server_params):
    read = MagicMock()
    write = MagicMock()
    yield read, write


@asynccontextmanager
async def _fake_sse_client(url):
    read = MagicMock()
    write = MagicMock()
    yield read, write


@asynccontextmanager
async def _fake_client_session(read, write):
    yield _make_fake_session()


class TestMCPClient:
    @pytest.fixture
    def stdio_config(self):
        return MCPServerConfig(
            name="test-stdio",
            command="echo",
            args=["hello"],
            transport="stdio",
        )

    @pytest.fixture
    def sse_config(self):
        return MCPServerConfig(
            name="test-sse",
            transport="sse",
            url="http://localhost:3001/sse",
        )

    async def test_not_connected_initially(self, stdio_config):
        client = MCPClient(stdio_config)
        assert client.is_connected is False
        assert client.name == "test-stdio"

    async def test_connect_disconnect_lifecycle(self, stdio_config):
        client = MCPClient(stdio_config)

        # Manually wire up internal state to simulate successful connect
        client._connected = True
        client._session = _make_fake_session()
        client._stack = AsyncMock()

        assert client.is_connected is True

        await client.disconnect()
        assert client.is_connected is False
        assert client._session is None

    async def test_list_tools_when_not_connected(self, stdio_config):
        client = MCPClient(stdio_config)
        tools = await client.list_tools()
        assert tools == []

    async def test_list_tools_when_connected(self, stdio_config):
        client = MCPClient(stdio_config)
        client._connected = True
        client._session = _make_fake_session()

        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "read_file"
        assert tools[0].server_name == "test-stdio"
        assert tools[0].description == "Read a file"
        assert tools[1].name == "write_file"

    async def test_call_tool_when_connected(self, stdio_config):
        client = MCPClient(stdio_config)
        client._connected = True
        session = _make_fake_session()
        client._session = session

        result = await client.call_tool("read_file", {"path": "/tmp/test"})
        session.call_tool.assert_awaited_once_with("read_file", {"path": "/tmp/test"})
        assert result.content == "tool result"

    async def test_call_tool_when_not_connected(self, stdio_config):
        client = MCPClient(stdio_config)
        with pytest.raises(RuntimeError, match="not connected"):
            await client.call_tool("read_file")

    async def test_disconnect_when_not_connected(self, stdio_config):
        client = MCPClient(stdio_config)
        # Should not raise
        await client.disconnect()
        assert client.is_connected is False

    async def test_double_disconnect(self, stdio_config):
        client = MCPClient(stdio_config)
        client._connected = True
        client._session = _make_fake_session()
        client._stack = AsyncMock()

        await client.disconnect()
        await client.disconnect()  # Should not raise
        assert client.is_connected is False


class TestMCPToolInfo:
    def test_creation(self):
        tool = MCPToolInfo(
            name="my_tool",
            server_name="my_server",
            description="Does things",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        assert tool.name == "my_tool"
        assert tool.server_name == "my_server"
        assert tool.description == "Does things"
        assert "properties" in tool.input_schema

    def test_defaults(self):
        tool = MCPToolInfo(name="t", server_name="s")
        assert tool.description == ""
        assert tool.input_schema == {}


async def _mock_connect_stdio(self):
    """Mock connect that sets up fake state."""
    self._connected = True
    self._session = _make_fake_session()
    self._stack = AsyncMock()
