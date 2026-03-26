"""MCPManager: lifecycle management for multiple MCP server connections."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sygen_bot.config import MCPConfig, MCPServerConfig
from sygen_bot.mcp.client import MCPClient, MCPToolInfo

logger = logging.getLogger(__name__)

_HEALTH_CHECK_INTERVAL = 30.0


@dataclass(slots=True)
class ServerHealth:
    """Health state of a single MCP server."""

    name: str
    connected: bool = False
    restart_count: int = 0
    last_error: str = ""


class MCPManager:
    """Manages multiple MCP server connections with health monitoring."""

    def __init__(self, config: MCPConfig) -> None:
        self._config = config
        self._clients: dict[str, MCPClient] = {}
        self._health: dict[str, ServerHealth] = {}
        self._tools_cache: list[MCPToolInfo] = []
        self._health_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Connect to all enabled servers and start the health loop."""
        for server_cfg in self._config.servers:
            if server_cfg.enabled:
                await self._connect_server(server_cfg)

        await self.refresh_tools()

        self._health_task = asyncio.create_task(self._health_loop())
        logger.info(
            "MCPManager started: %d server(s), %d tool(s)",
            len(self._clients),
            len(self._tools_cache),
        )

    async def stop(self) -> None:
        """Disconnect all servers and cancel the health loop."""
        if self._health_task is not None:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

        for client in list(self._clients.values()):
            await client.disconnect()
        self._clients.clear()
        self._health.clear()
        self._tools_cache.clear()
        logger.info("MCPManager stopped")

    async def restart_server(self, name: str) -> None:
        """Restart a specific MCP server by name."""
        if name in self._clients:
            await self._clients[name].disconnect()

        cfg = self._find_server_config(name)
        if cfg is None:
            logger.warning("Cannot restart unknown MCP server '%s'", name)
            return

        await self._connect_server(cfg)
        await self.refresh_tools()

    async def add_server(self, config: MCPServerConfig) -> None:
        """Add and connect a new MCP server at runtime."""
        self._config.servers.append(config)
        if config.enabled:
            await self._connect_server(config)
            await self.refresh_tools()

    async def remove_server(self, name: str) -> None:
        """Disconnect and remove an MCP server."""
        if name in self._clients:
            await self._clients[name].disconnect()
            del self._clients[name]
        self._health.pop(name, None)
        self._config.servers = [s for s in self._config.servers if s.name != name]
        await self.refresh_tools()

    def get_all_tools(self) -> list[MCPToolInfo]:
        """Return cached tools from all connected servers."""
        return list(self._tools_cache)

    async def refresh_tools(self) -> list[MCPToolInfo]:
        """Re-fetch tools from all connected servers and update cache."""
        tools: list[MCPToolInfo] = []
        for client in self._clients.values():
            if client.is_connected:
                try:
                    tools.extend(await client.list_tools())
                except Exception:
                    logger.warning(
                        "Failed to list tools from '%s'",
                        client.name,
                        exc_info=True,
                    )
        self._tools_cache = tools
        return list(tools)

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool on a specific server."""
        client = self._clients.get(server_name)
        if client is None or not client.is_connected:
            msg = f"MCP server '{server_name}' is not connected"
            raise RuntimeError(msg)
        return await client.call_tool(tool_name, arguments)

    def server_status(self) -> dict[str, ServerHealth]:
        """Return health status for all known servers."""
        return dict(self._health)

    async def _connect_server(self, config: MCPServerConfig) -> None:
        """Connect to a single MCP server with timeout."""
        client = MCPClient(config)
        health = self._health.get(config.name, ServerHealth(name=config.name))
        try:
            await asyncio.wait_for(client.connect(), timeout=config.startup_timeout_seconds)
            health.connected = True
            health.last_error = ""
        except Exception as exc:
            health.connected = False
            health.last_error = str(exc)[:200]
            logger.error("Failed to connect MCP server '%s': %s", config.name, exc)
        self._clients[config.name] = client
        self._health[config.name] = health

    async def _health_loop(self) -> None:
        """Periodically check server health and restart crashed servers."""
        while True:
            await asyncio.sleep(_HEALTH_CHECK_INTERVAL)
            for name, client in list(self._clients.items()):
                health = self._health.get(name)
                if health is None:
                    continue
                cfg = self._find_server_config(name)
                if cfg is None:
                    continue

                if not client.is_connected and cfg.auto_restart:
                    logger.info("Restarting MCP server '%s'...", name)
                    health.restart_count += 1
                    await asyncio.sleep(cfg.restart_delay_seconds)
                    await self._connect_server(cfg)

                health.connected = client.is_connected

    def _find_server_config(self, name: str) -> MCPServerConfig | None:
        """Find server config by name."""
        for cfg in self._config.servers:
            if cfg.name == name:
                return cfg
        return None
