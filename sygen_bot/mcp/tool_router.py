"""ToolRouter: bridges MCP tools into CLI provider configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sygen_bot.mcp.manager import MCPManager

logger = logging.getLogger(__name__)


class ToolRouter:
    """Routes MCP tools into CLI provider configurations.

    Generates MCP config files in the Claude CLI format and provides
    helper methods for prompt injection and tool dispatch.
    """

    def __init__(self, manager: MCPManager, workspace_dir: Path) -> None:
        self._manager = manager
        self._workspace_dir = workspace_dir

    def generate_mcp_config_file(self) -> Path:
        """Generate a JSON config file in Claude CLI ``--mcp-config`` format.

        Returns the path to the generated file.
        """
        tools = self._manager.get_all_tools()
        servers: dict[str, dict[str, Any]] = {}

        for tool in tools:
            if tool.server_name not in servers:
                servers[tool.server_name] = {"tools": []}
            servers[tool.server_name]["tools"].append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            })

        # Build Claude CLI mcp config format: {"mcpServers": {name: {command, args, env}}}
        mcp_servers: dict[str, dict[str, Any]] = {}
        for cfg in self._manager._config.servers:
            if not cfg.enabled:
                continue
            if cfg.transport == "sse":
                mcp_servers[cfg.name] = {
                    "url": cfg.url,
                    "type": "sse",
                }
            else:
                entry: dict[str, Any] = {
                    "command": cfg.command,
                    "args": cfg.args,
                }
                if cfg.env:
                    entry["env"] = cfg.env
                mcp_servers[cfg.name] = entry

        config_data = {"mcpServers": mcp_servers}
        config_path = self._workspace_dir / ".mcp.json"
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        logger.info("Generated MCP config at %s (%d servers)", config_path, len(mcp_servers))
        return config_path

    def get_cli_parameters(self, provider: str) -> list[str]:
        """Return additional CLI arguments for MCP integration.

        Only applicable to Claude provider (``--mcp-config``).
        """
        if provider != "claude":
            return []

        tools = self._manager.get_all_tools()
        if not tools:
            return []

        config_path = self.generate_mcp_config_file()
        return ["--mcp-config", str(config_path)]

    def get_tool_descriptions_for_prompt(self) -> str:
        """Build a human-readable summary of available MCP tools for system prompts."""
        tools = self._manager.get_all_tools()
        if not tools:
            return ""

        lines = ["Available MCP tools:"]
        for tool in tools:
            desc = f"  - {tool.server_name}/{tool.name}"
            if tool.description:
                desc += f": {tool.description}"
            lines.append(desc)
        return "\n".join(lines)

    async def handle_tool_call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Dispatch a tool call to the correct MCP server.

        Looks up the tool by name across all servers.
        """
        for tool in self._manager.get_all_tools():
            if tool.name == tool_name:
                return await self._manager.call_tool(tool.server_name, tool_name, arguments)

        msg = f"MCP tool '{tool_name}' not found on any server"
        raise ValueError(msg)
