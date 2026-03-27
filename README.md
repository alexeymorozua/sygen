# Sygen

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://python.org)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/timedesign)

**AI assistant framework** with multi-agent orchestration, background tasks, and persistent memory.

Telegram-first personal AI agent that runs CLI tools (Claude Code, Codex, Gemini) and manages complex workflows autonomously.

## Features

### Core
- **Multi-agent system** — supervisor + sub-agents, each with own bot and workspace
- **Background task delegation** — offload long work to autonomous agents, keep chatting, get results back
- **Persistent memory** — modular memory system with Always Load / On Demand separation
- **Named sessions** — multiple isolated conversation contexts per chat
- **Inter-agent communication** — sync and async messaging between agents with shared knowledge base

### Transports & Providers
- **Telegram** (primary) + **Matrix** support
- **Claude Code**, **Codex CLI**, **Gemini CLI** — pluggable AI backends
- **Streaming output** — real-time response delivery with configurable buffering

### MCP (Model Context Protocol)
- **Native MCP client** — connects to any MCP server, discovers tools, routes calls
- **3000+ integrations** — GitHub, Google Drive, Slack, Docker, databases, and more
- **Auto-lifecycle** — starts servers on boot, health checks every 30s, auto-restart on crash
- **Hot-reload** — add/remove servers without restarting the bot
- **`/mcp` command** — list servers, check status, refresh tools from Telegram

### Skill Marketplace (ClawHub)
- **13,000+ community skills** — search and install from OpenClaw's ClawHub registry
- **Security scanning** — static analysis (20 suspicious patterns) + VirusTotal API before every install
- **User always decides** — full security report shown, install only on explicit confirmation
- **Zero dependencies** — no npm/OpenClaw required, pure HTTP API integration
- **`/skill` command** — search, install, list, remove from Telegram

### Automation
- **Cron scheduler** — recurring tasks with timezone support
- **Webhook server** — HTTP endpoints that trigger agent actions
- **Docker sandbox** — optional secure execution for untrusted code
- **Silent output** — `[SILENT]` marker lets cron/webhook tasks suppress delivery when nothing to report

### Observability
- **Execution traces** — every cron, task, and webhook run is logged to SQLite (`traces.db`)
- **`/logs` command** — view recent traces, filter by type (`/logs cron`), errors (`/logs errors`), or name
- **Auto-rotation** — traces older than 30 days cleaned up automatically, no maintenance needed

### Built-in Tools (Defaults)
- **Web search** — Perplexity Sonar (primary) + DuckDuckGo (fallback, no API key needed)
- **Perplexity deep search** — sonar-pro for research-heavy queries
- **Audio transcription** — local whisper.cpp, no external APIs
- **YouTube analysis** — metadata, subtitles, frame extraction, audio transcription
- **File converter** — Markdown→PDF, DOCX→TXT, XLSX→CSV, HEIC→JPG
- **Large file sender** — local fileshare (auto-detect) with 0x0.st fallback
- **Quick notes** — structured idea capture template

### UX
- **Mobile-friendly tables** — Markdown tables are auto-converted to grouped lists for Telegram readability
- **Emoji status reactions** — track agent progress on your original message
- **Configurable streaming** — three combined modes (see table below)
- **Technical footer** — optional model, tokens, cost, duration display
- **Inline buttons** — quick-reply buttons in Telegram messages

#### Streaming & Reaction Modes

| Mode | Config | Reactions | Text delivery |
|---|---|---|---|
| **Quiet** | `streaming.enabled: false`, `scene.reaction_style: "seen"` | 👀 → ✅ | Single message after completion |
| **Full streaming** | `streaming.enabled: true`, `scene.reaction_style: "detailed"` | 👀 → 🤔 → ⚙️ → 📦 → ✅ | Real-time, dynamically updated |
| **Buffered** | `streaming.enabled: true`, `streaming.buffered: true`, `scene.reaction_style: "detailed"` | 👀 → 🤔 → ⚙️ → 📦 → ✅ | Single message after completion |

**Reaction emoji meaning:**
- 👀 — message received, processing started
- 🤔 — model is thinking
- ⚙️ — executing a tool (bash, file read, etc.)
- 📦 — context compacting (long conversation optimization)
- ✅ — response complete

**Buffered mode** is the recommended choice when you want to see what the agent is doing (via reactions) but prefer clean, non-flickering text delivery. Internally, the agent streams events for reaction updates, but text is collected in a buffer and sent as a single message at the end.

Set `scene.reaction_style: "off"` to disable all reactions.

### Maintenance (Built-in)
- **Auto file cleanup** — daily removal of old media files, output, tasks, and cron results (configurable retention)
- **Real-time memory consolidation** — module size enforcement (120-line limit) via hook system, no cron needed

### Memory System
- **Modular structure** — separate files per topic (user, decisions, infrastructure, tools, crons)
- **Always Load** modules injected at session start (user profile, key decisions)
- **On Demand** modules loaded when relevant (infrastructure, tool configs)
- **Auto-reflection** — periodic memory review and cleanup

## Quick Start

```bash
pip install -e .
sygen
```

On first run, Sygen creates a workspace at `~/.sygen/` with default tools, memory templates, and config.

## Configuration

All settings in `~/.sygen/config/config.json`. Key sections:

| Section | What it controls |
|---|---|
| `model` | AI provider and model name |
| `streaming` | Real-time output (enabled, buffered, min/max chars, idle timeout) |
| `scene` | Emoji reactions (`reaction_style`: off/seen/detailed), technical footer |
| `cleanup` | Auto file cleanup (enabled, retention days per category) |
| `timeouts` | Response timeouts per mode |
| `media` | Image quality, audio transcription |
| `mcp` | MCP servers (enabled, server list) |
| `skill_marketplace` | ClawHub integration (enabled, VirusTotal API key) |

## Architecture

```
User (Telegram/Matrix)
  ↓
Sygen Bot (Python, aiogram/matrix-nio)
  ↓
Orchestrator → CLI Service → AI Provider (Claude/Codex/Gemini)
  ↓                ↓
Sessions      Background Tasks (autonomous agents)
  ↓                ↓
Memory        Inter-Agent Bus (sync/async messaging)
  ↓
Cron / Webhooks / Tools
```

## MCP Setup

Sygen includes a native MCP client. To connect MCP servers, add to `config.json`:

```json
{
  "mcp": {
    "enabled": true,
    "servers": [
      {
        "name": "github",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx" }
      },
      {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/you/projects"]
      }
    ]
  }
}
```

Per-agent MCP servers can be configured in `agents.json` under the `mcp` field.

**Commands:**
- `/mcp list` — show connected servers and their tools
- `/mcp status` — health check of each server
- `/mcp refresh` — re-discover tools from all servers

**Server options:**

| Field | Default | Description |
|---|---|---|
| `name` | required | Unique server identifier |
| `command` | required | Executable (npx, python3, etc.) |
| `args` | `[]` | Command arguments |
| `env` | `{}` | Environment variables |
| `transport` | `"stdio"` | `"stdio"` for local, `"sse"` for remote |
| `url` | `""` | Server URL (SSE transport only) |
| `enabled` | `true` | Enable/disable without removing |
| `auto_restart` | `true` | Restart on crash |

MCP config supports hot-reload — changes to `config.json` are picked up without restarting the bot.

## Skill Marketplace Setup

Search and install community skills from ClawHub with built-in security scanning.

```json
{
  "skill_marketplace": {
    "enabled": true,
    "virustotal_api_key": "your-vt-api-key"
  }
}
```

VirusTotal API key is optional (free at virustotal.com). Without it, only static analysis runs.

**Commands:**
- `/skill search <query>` — search ClawHub for skills
- `/skill install <name>` — download, scan, show report, confirm install
- `/skill list` — list installed skills
- `/skill remove <name>` — remove a skill

**Install flow:**
1. Skill is downloaded to a temp directory
2. Static analysis scans all scripts for suspicious patterns (eval, exec, network calls, sensitive paths)
3. VirusTotal checks file hashes against 70+ antivirus engines
4. Security report is shown with clear status indicators
5. User confirms or cancels — nothing is installed without approval

## Provider-Neutral Design

Sygen does not hardcode any AI provider or model in defaults. All crons, tools, and templates use `null` for provider/model fields — the user's configured backend is used automatically. Switching from Claude to Gemini requires only a config change, no code edits.

## Updates

```bash
pip install --upgrade sygen
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By opening a PR you agree to the [CLA](CLA.md).

## License

[BSL 1.1](LICENSE) — free for personal use and small teams (<5 people). Converts to MIT on 2030-03-27.
