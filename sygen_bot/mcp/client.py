"""MCP client: thin wrapper around the MCP Python SDK."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from sygen_bot.config import MCPServerConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MCPToolInfo:
    """Descriptor for a single tool exposed by an MCP server."""

    name: str
    server_name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient:
    """Manages a connection to a single MCP server.

    Uses ``contextlib.AsyncExitStack`` to manage the nested async context
    managers from the MCP SDK (transport + session).
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._stack: AsyncExitStack | None = None
        self._session: Any = None  # mcp.ClientSession
        self._connected = False

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Start transport and initialize the MCP session."""
        if self._connected:
            return

        try:
            from mcp import ClientSession
        except ImportError as exc:
            msg = (
                "mcp package not installed. "
                "Install with: pip install sygen[mcp]"
            )
            raise ImportError(msg) from exc

        stack = AsyncExitStack()
        try:
            if self._config.transport == "sse":
                from mcp.client.sse import sse_client

                read_stream, write_stream = await stack.enter_async_context(
                    sse_client(self._config.url)
                )
            else:
                from mcp.client.stdio import stdio_client
                from mcp import StdioServerParameters

                server_params = StdioServerParameters(
                    command=self._config.command,
                    args=self._config.args,
                    env=self._config.env or None,
                )
                read_stream, write_stream = await stack.enter_async_context(
                    stdio_client(server_params)
                )

            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()

            self._stack = stack
            self._session = session
            self._connected = True
            logger.info("MCP server '%s' connected (%s)", self.name, self._config.transport)
        except Exception:
            await stack.aclose()
            raise

    async def disconnect(self) -> None:
        """Gracefully close the MCP session and transport."""
        if not self._connected:
            return
        self._connected = False
        self._session = None
        if self._stack:
            try:
                await self._stack.aclose()
            except Exception:
                logger.warning("Error closing MCP stack for '%s'", self.name, exc_info=True)
            self._stack = None
        logger.info("MCP server '%s' disconnected", self.name)

    async def list_tools(self) -> list[MCPToolInfo]:
        """List tools available on this server."""
        if not self._connected or self._session is None:
            return []
        result = await self._session.list_tools()
        return [
            MCPToolInfo(
                name=tool.name,
                server_name=self.name,
                description=getattr(tool, "description", "") or "",
                input_schema=getattr(tool, "inputSchema", {}) or {},
            )
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool on this server and return the result."""
        if not self._connected or self._session is None:
            msg = f"MCP server '{self.name}' is not connected"
            raise RuntimeError(msg)
        result = await self._session.call_tool(name, arguments or {})
        return result
