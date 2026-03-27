# Sygen

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

### Smart Model Routing
- **Auto model selection** — routes messages to the right model tier by complexity
- **LLM classifier** — uses a cheap model (Haiku/Flash/4o-mini) to classify each message as light/medium/heavy
- **Per-provider tiers** — Claude (Haiku/Sonnet/Opus), Codex (4o-mini/4o/o3), Gemini (Flash/Pro)
- **User override** — `@opus` or `@haiku` always takes priority over routing
- **Optional** — disabled by default, requires a separate API key for the classifier
- **Zero overhead when off** — no extra calls, no latency

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

### Built-in Tools (Defaults)
- **Web search** — Perplexity Sonar (primary) + DuckDuckGo (fallback, no API key needed)
- **Perplexity deep search** — sonar-pro for research-heavy queries
- **Audio transcription** — local whisper.cpp, no external APIs
- **YouTube analysis** — metadata, subtitles, frame extraction, audio transcription
- **File converter** — Markdown→PDF, DOCX→TXT, XLSX→CSV, HEIC→JPG
- **Large file sender** — local fileshare (auto-detect) with 0x0.st fallback
- **Quick notes** — structured idea capture template

### UX
- **Emoji status reactions** — three modes:
  - `off` — no reactions
  - `seen` (default) — 👀 on receipt, ✅ on completion
  - `detailed` — 👀 → 🤔 thinking → ⚙️ tool use → 📦 compacting → ✅ done
- **Configurable streaming** — enable/disable intermediate message updates
- **Technical footer** — optional model, tokens, cost, duration display
- **Inline buttons** — quick-reply buttons in Telegram messages

### Maintenance (Out of the Box)
Four maintenance crons ship enabled by default:
- **Weekly cleanup** — remove one-shot crons, orphaned sessions, old temp files (Sunday 10:00)
- **Monthly memory cleanup** — deduplicate and merge memory entries (15th, 10:00)
- **Monthly memory review** — deep audit for contradictions and staleness (1st, 10:00)
- **Daily security audit** — check tokens, file permissions, disk usage, bot health (08:00)

All crons inherit provider and model from user config — works with Claude, Gemini, or any supported backend.

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

On first run, Sygen creates a workspace at `~/.ductor/` with default tools, memory templates, and config.

## Configuration

All settings in `~/.ductor/config/config.json`. Key sections:

| Section | What it controls |
|---|---|
| `model` | AI provider and model name |
| `streaming` | Real-time output (enabled, min/max chars, idle timeout) |
| `scene` | Emoji reactions (`reaction_style`), technical footer |
| `timeouts` | Response timeouts per mode |
| `media` | Image quality, audio transcription |
| `mcp` | MCP servers (enabled, server list) |
| `routing` | Smart model routing (enabled, API key, tiers) |
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

## Smart Model Routing

Automatically route messages to the optimal model based on complexity. Requires a separate API key for the classifier model.

```json
{
  "routing": {
    "enabled": true,
    "api_key": "sk-ant-xxx",
    "classifier_provider": "anthropic",
    "classifier_model": "claude-haiku-4-5-20251001",
    "tiers": {
      "claude": { "light": "haiku", "medium": "sonnet", "heavy": "opus" },
      "codex":  { "light": "gpt-4o-mini", "medium": "gpt-4o", "heavy": "o3" },
      "gemini": { "light": "flash", "medium": "pro", "heavy": "pro" }
    }
  }
}
```

**How it works:**
1. User sends a message
2. Classifier (cheap API call, ~100ms) rates complexity: light / medium / heavy
3. Message is routed to the matching model for the active provider
4. Conversation context is preserved (same CLI session)

**Override:** `@opus`, `@haiku`, or `/model` always takes priority over routing.

**Cost:** ~$0.0001 per classification (~$0.30/month at 100 messages/day).

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
/upgrade          # pulls latest from GitHub (git pull --ff-only)
```

## Upstream Sync

Forked from [Ductor](https://github.com/PleasePrompto/ductor). Original tracked as `upstream` remote:

```bash
git fetch upstream
git log upstream/main --oneline    # review changes
git cherry-pick <commit>           # pick what you need
```

## License

[MIT](LICENSE)
