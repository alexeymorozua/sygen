# MCP Integration

Native [Model Context Protocol](https://modelcontextprotocol.io/) client. Connects sygen to external tool servers (databases, APIs, file systems) and exposes their tools to CLI providers.

## Files

- `sygen_bot/mcp/client.py`: `MCPClient` — single-server connection wrapper (stdio + SSE transports)
- `sygen_bot/mcp/manager.py`: `MCPManager` — multi-server lifecycle, health monitoring, auto-restart
- `sygen_bot/mcp/tool_router.py`: `ToolRouter` — bridges MCP tools into CLI provider config (`--mcp-config`)
- `sygen_bot/mcp/commands.py`: `/mcp` Telegram command handler

## Architecture

```text
User → /mcp → MCPManager → MCPClient(s) → MCP Server(s)
                   ↓
              ToolRouter → .mcp.json → Claude CLI --mcp-config
```

**MCPClient** manages a single server connection via `AsyncExitStack`. Supports two transports:
- `stdio` — launches a local process (command + args)
- `sse` — connects to a remote HTTP SSE endpoint

**MCPManager** handles multiple servers:
- Connects all enabled servers at startup
- Caches tool listings for fast lookup
- Runs a health check loop (30s interval)
- Auto-restarts crashed servers (configurable per server)

**ToolRouter** generates a `.mcp.json` config file in Claude CLI format and injects `--mcp-config` into CLI arguments. Also provides `get_tool_descriptions_for_prompt()` for system prompt injection.

## Configuration

```json
{
  "mcp": {
    "enabled": true,
    "servers": [
      {
        "name": "filesystem",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"],
        "enabled": true,
        "auto_restart": true,
        "startup_timeout_seconds": 10,
        "restart_delay_seconds": 2
      },
      {
        "name": "remote-api",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
        "enabled": true
      }
    ]
  }
}
```

## Telegram commands

- `/mcp` — list connected servers and their tools
- `/mcp status` — detailed health status (connected/disconnected, restart count, errors)
- `/mcp refresh` — re-fetch tools from all servers
- `/mcp help` — command reference

## Installation

MCP requires the optional `mcp` dependency:

```bash
pip install sygen[mcp]
```

The `mcp` package is imported lazily — sygen runs without it, and shows a clear error when MCP is enabled but the package is missing.
