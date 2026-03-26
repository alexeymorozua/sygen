"""Tests for MCP config models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sygen_bot.config import AgentConfig, MCPConfig, MCPServerConfig


class TestMCPServerConfig:
    def test_defaults(self):
        cfg = MCPServerConfig(name="test-server")
        assert cfg.name == "test-server"
        assert cfg.command == ""
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.transport == "stdio"
        assert cfg.url == ""
        assert cfg.enabled is True
        assert cfg.auto_restart is True
        assert cfg.restart_delay_seconds == 5.0
        assert cfg.startup_timeout_seconds == 30.0

    def test_stdio_config(self):
        cfg = MCPServerConfig(
            name="fs",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            env={"NODE_ENV": "production"},
        )
        assert cfg.command == "npx"
        assert len(cfg.args) == 3
        assert cfg.env["NODE_ENV"] == "production"

    def test_sse_config(self):
        cfg = MCPServerConfig(
            name="remote",
            transport="sse",
            url="http://localhost:3001/sse",
        )
        assert cfg.transport == "sse"
        assert cfg.url == "http://localhost:3001/sse"

    def test_disabled_server(self):
        cfg = MCPServerConfig(name="disabled", enabled=False)
        assert cfg.enabled is False

    def test_name_required(self):
        with pytest.raises(ValidationError):
            MCPServerConfig()  # type: ignore[call-arg]


class TestMCPConfig:
    def test_defaults(self):
        cfg = MCPConfig()
        assert cfg.enabled is False
        assert cfg.servers == []

    def test_with_servers(self):
        cfg = MCPConfig(
            enabled=True,
            servers=[
                MCPServerConfig(name="a", command="cmd-a"),
                MCPServerConfig(name="b", command="cmd-b"),
            ],
        )
        assert cfg.enabled is True
        assert len(cfg.servers) == 2
        assert cfg.servers[0].name == "a"
        assert cfg.servers[1].name == "b"


class TestAgentConfigMCP:
    def test_mcp_default_disabled(self):
        cfg = AgentConfig()
        assert cfg.mcp.enabled is False
        assert cfg.mcp.servers == []

    def test_mcp_from_dict(self):
        cfg = AgentConfig(
            mcp={
                "enabled": True,
                "servers": [
                    {"name": "test", "command": "echo", "args": ["hello"]},
                ],
            }
        )
        assert cfg.mcp.enabled is True
        assert len(cfg.mcp.servers) == 1
        assert cfg.mcp.servers[0].name == "test"

    def test_mcp_backward_compat(self):
        """Config without mcp key should work fine."""
        cfg = AgentConfig(**{"model": "sonnet"})
        assert cfg.mcp.enabled is False
