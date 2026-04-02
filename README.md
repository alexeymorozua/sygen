# Sygen

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://python.org)
[![Version 1.1.9](https://img.shields.io/badge/Version-1.1.9-brightgreen.svg)](https://pypi.org/project/sygen/)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/timedesign)

**Self-hosted AI assistant framework with multi-agent orchestration, background tasks, and persistent memory.**

### Why Sygen?

Most AI chatbot frameworks give you a single bot that answers questions. Sygen gives you an autonomous agent system that runs on your own hardware, coordinates multiple AI backends (Claude, Codex, Gemini), and manages long-running workflows without babysitting. It persists memory across sessions, schedules recurring tasks, connects to 3000+ external services via MCP, and lets you spin up sub-agents that operate independently — all from a Telegram or Matrix chat.

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
- **Cron scheduler** — recurring tasks with timezone support, plus `script_mode` for direct script execution without LLM
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
| **Quiet** | `streaming.enabled: false`, `scene.reaction_style: "seen"` | 👀 → 👌 | Single message after completion |
| **Full streaming** | `streaming.enabled: true`, `scene.reaction_style: "detailed"` | 👀 → 🤔 → ✍️ → 💯 → 👌 | Real-time, dynamically updated |
| **Buffered** | `streaming.enabled: true`, `streaming.buffered: true`, `scene.reaction_style: "detailed"` | 👀 → 🤔 → ✍️ → 💯 → 👌 | Single message after completion |

**Reaction emoji meaning:**
- 👀 — message received, processing started
- 🤔 — model is thinking
- ✍️ — executing a tool (bash, file read, etc.)
- 💯 — context compacting (long conversation optimization)
- 👌 — response complete

**Buffered mode** is the recommended choice when you want to see what the agent is doing (via reactions) but prefer clean, non-flickering text delivery. Internally, the agent streams events for reaction updates, but text is collected in a buffer and sent as a single message at the end.

Set `scene.reaction_style: "off"` to disable all reactions.

### Maintenance (Built-in)
- **Auto file cleanup** — daily removal of old media files, output, tasks, and cron results (configurable retention)
- **Memory maintenance** — automatic deduplication, module size enforcement, orphan session cleanup, one-shot cron removal
- **Default crons** — monthly memory review (LLM-based quality check) and daily security audit are installed as crons since they require LLM intelligence

### Memory System
- **Modular structure** — separate files per topic (user, decisions, infrastructure, tools, crons)
- **Always Load** modules injected at session start (user profile, key decisions)
- **On Demand** modules loaded when relevant (infrastructure, tool configs)
- **Auto-reflection** — periodic memory review and cleanup

## Quick Start

### Prerequisites

- Python 3.11 or higher
- A Telegram bot token (create one via [@BotFather](https://t.me/BotFather))
- At least one AI CLI backend installed: [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex CLI](https://github.com/openai/codex), or [Gemini CLI](https://github.com/google-gemini/gemini-cli)

### 1. Install Sygen

```bash
pip install sygen
```

### 2. Create the config directory and minimal config

```bash
mkdir -p ~/.sygen/config
cat > ~/.sygen/config/config.json << 'EOF'
{
  "telegram_token": "YOUR_TELEGRAM_BOT_TOKEN",
  "model": "sonnet",
  "allowed_user_ids": [YOUR_TELEGRAM_USER_ID]
}
EOF
```

Replace `YOUR_TELEGRAM_BOT_TOKEN` and `YOUR_TELEGRAM_USER_ID` with your actual values. Find your user ID by messaging [@userinfobot](https://t.me/userinfobot) on Telegram.

### 3. Start Sygen

```bash
sygen
```

On first run, Sygen creates a workspace at `~/.sygen/` with default tools, memory templates, and config.

### 4. Send your first message

Open your bot in Telegram and send any message. Sygen will respond using the configured AI backend.

## Usage Examples

### Basic bot setup (minimal config.json)

```json
{
  "telegram_token": "123456:ABC-DEF...",
  "model": "sonnet",
  "allowed_user_ids": [123456789],
  "streaming": {
    "enabled": true,
    "buffered": true
  },
  "scene": {
    "reaction_style": "detailed"
  }
}
```

### Enable RAG pipeline

Add a `rag` section to `config.json` to let the agent search and reference your local documents:

```json
{
  "rag": {
    "enabled": true,
    "chunk_size": 512,
    "top_k_final": 5,
    "reranker_model": "antoinelouis/colbert-xm"
  }
}
```

The RAG pipeline indexes workspace files and memory modules automatically — no external APIs or vector databases required. Uses BM25 + vector hybrid search with ColBERT v2 reranking. Supported file types: `.md`, `.txt`, `.yaml`, `.yml` (configurable via `workspace_glob_patterns`).

### Set up a cron task

From your Telegram chat with the bot:

```
You:   Create a cron task that checks Hacker News top stories every morning at 8am
       and sends me a summary of the top 5.

Sygen: Created cron task "hn-morning" — runs daily at 08:00 (Europe/Berlin).
       Next run: tomorrow at 08:00.

You:   /cron list

Sygen: Active cron tasks:
       • hn-morning — daily 08:00 — Check HN top stories
       • memory-review — monthly — Memory quality review
```

Cron tasks run as autonomous agent sessions with full tool access. Use `[SILENT]` in the task description to suppress output when there is nothing to report.

**Script mode** — for tasks that just run a script (dashboards, reports, monitoring), use `script_mode` to bypass the LLM agent entirely. The script's stdout is sent directly to Telegram — no tokens consumed, 100% reliable:

```json
{
  "id": "business-dashboard",
  "script_mode": true,
  "script": "scripts/dashboard.py",
  "schedule": "0 19 * * *"
}
```

### Multi-agent setup

Define sub-agents in `~/.sygen/agents.json`. Each agent gets its own Telegram bot, workspace, and memory:

```json
[
  {
    "name": "researcher",
    "telegram_token": "111111:AAA-BBB...",
    "model": "sonnet",
    "allowed_user_ids": [123456789]
  },
  {
    "name": "coder",
    "telegram_token": "222222:CCC-DDD...",
    "model": "o4-mini",
    "allowed_user_ids": [123456789]
  }
]
```

The main agent can delegate tasks to sub-agents via sync or async messaging. Each sub-agent also works as a standalone bot that you can chat with directly.

## Configuration

All settings in `~/.sygen/config/config.json`. Key sections:

| Section | What it controls |
|---|---|
| `provider` / `model` | AI backend (claude/codex/gemini) and model name (sonnet, opus, flash) |
| `streaming` | Real-time output (enabled, buffered, min/max chars, idle timeout) |
| `scene` | Emoji reactions (`reaction_style`: off/seen/detailed), technical footer |
| `cleanup` | Auto file cleanup (enabled, retention days per category) |
| `memory` | Memory maintenance (enabled, module line limit, session max age, check hour) |
| `timeouts` | Response timeouts per mode |
| `image` / `transcription` | Image quality settings, audio transcription (whisper model, language) |
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

## Comparison

| Feature | Sygen | MemGPT / Letta | OpenClaw | Typical chatbot frameworks |
|---|---|---|---|---|
| Self-hosted, runs on your machine | Yes | Yes | Yes | Varies |
| Multi-agent orchestration | Built-in (supervisor + sub-agents) | Single agent | Single agent | Usually not |
| Persistent memory (cross-session) | Modular file-based, always load / on demand | Tiered memory (core/archival/recall) | Via skills | Manual or none |
| RAG pipeline (local, no external APIs) | Built-in | Requires external vector DB | No | Requires setup |
| Background task delegation | Autonomous agents in separate processes | No | No | No |
| Cron / scheduled tasks | Native, timezone-aware, with silent mode | No | No | Rarely |
| Webhooks (inbound HTTP triggers) | Native | No | No | Rarely |
| MCP protocol (3000+ integrations) | Native client with auto-lifecycle | No | No | No |
| Skill marketplace (13k+ skills) | ClawHub with security scanning | No | ClawHub (origin) | No |
| Multiple AI backends | Claude Code, Codex CLI, Gemini CLI | OpenAI only | Claude Code | Usually one |
| Transport | Telegram + Matrix | Web UI | CLI only | Web / API |
| Streaming with reaction indicators | Three configurable modes | Basic streaming | No | Varies |
| Execution traces / observability | SQLite-backed `/logs` command | Basic logging | No | Varies |

## Documentation

Full documentation is available at [https://alexeymorozua.github.io/sygen/](https://alexeymorozua.github.io/sygen/).

Covers installation, configuration reference, agent setup, tool development, memory system internals, MCP integration, and skill creation.

## Updates

```bash
pip install --upgrade sygen
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By opening a PR you agree to the [CLA](CLA.md).

## License

[BSL 1.1](LICENSE) — free for personal use and small teams (<5 people). Converts to MIT on 2030-03-27.
