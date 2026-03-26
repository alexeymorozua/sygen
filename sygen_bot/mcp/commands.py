"""Telegram command handler for /mcp: MCP server management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sygen_bot.orchestrator.registry import OrchestratorResult
from sygen_bot.text.response_format import SEP, fmt

if TYPE_CHECKING:
    from sygen_bot.orchestrator.core import Orchestrator
    from sygen_bot.session.key import SessionKey

logger = logging.getLogger(__name__)

_STATUS_EMOJI = {
    True: "●",
    False: "✖",
}

_HELP_TEXT = fmt(
    "**MCP Commands**",
    SEP,
    (
        "`/mcp` — list servers and tools\n"
        "`/mcp status` — server health status\n"
        "`/mcp refresh` — re-fetch tools from all servers\n"
        "`/mcp help` — this help"
    ),
)


async def cmd_mcp(orch: Orchestrator, _key: SessionKey, text: str) -> OrchestratorResult:
    """Handle /mcp command and subcommands."""
    manager = orch._mcp_manager
    if manager is None:
        return OrchestratorResult(
            text="MCP is not enabled. Set `mcp.enabled: true` in config.json."
        )

    parts = text.strip().split(None, 1)
    sub = parts[1].strip().lower() if len(parts) > 1 else ""

    if sub == "help":
        return OrchestratorResult(text=_HELP_TEXT)

    if sub == "status":
        return _status(manager)

    if sub == "refresh":
        return await _refresh(manager)

    # Default: list servers and tools
    return _list(manager)


def _list(manager: object) -> OrchestratorResult:
    """List all MCP servers and their tools."""
    from sygen_bot.mcp.manager import MCPManager

    assert isinstance(manager, MCPManager)

    status = manager.server_status()
    tools = manager.get_all_tools()

    if not status:
        return OrchestratorResult(text=fmt("**MCP Servers**", SEP, "No servers configured."))

    lines: list[str] = []
    for name, health in sorted(status.items()):
        emoji = _STATUS_EMOJI.get(health.connected, "?")
        server_tools = [t for t in tools if t.server_name == name]
        tool_names = ", ".join(t.name for t in server_tools) or "no tools"
        lines.append(f"  {emoji} **{name}** — {tool_names}")

    return OrchestratorResult(
        text=fmt(
            f"**MCP Servers** ({len(tools)} tools)",
            SEP,
            "\n".join(lines),
        )
    )


def _status(manager: object) -> OrchestratorResult:
    """Show detailed server health status."""
    from sygen_bot.mcp.manager import MCPManager

    assert isinstance(manager, MCPManager)

    status = manager.server_status()
    if not status:
        return OrchestratorResult(text=fmt("**MCP Status**", SEP, "No servers configured."))

    lines: list[str] = []
    for name, health in sorted(status.items()):
        emoji = _STATUS_EMOJI.get(health.connected, "?")
        state = "connected" if health.connected else "disconnected"
        info = f"  {emoji} **{name}** — {state}"
        if health.restart_count > 0:
            info += f" (restarts: {health.restart_count})"
        if health.last_error:
            info += f"\n      Error: {health.last_error[:100]}"
        lines.append(info)

    return OrchestratorResult(text=fmt("**MCP Status**", SEP, "\n".join(lines)))


async def _refresh(manager: object) -> OrchestratorResult:
    """Refresh tools from all connected servers."""
    from sygen_bot.mcp.manager import MCPManager

    assert isinstance(manager, MCPManager)

    tools = await manager.refresh_tools()
    return OrchestratorResult(
        text=f"Refreshed MCP tools: {len(tools)} tool(s) from {len(manager.server_status())} server(s)."
    )
