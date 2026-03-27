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

### Smart Routing
- **Auto model selection** — routes messages to the right model tier by complexity
- **Auto background delegation** — long-running tasks are automatically sent to background workers
- **LLM classifier** — one cheap call (Haiku/Flash/4o-mini) decides both model and execution mode
- **Per-provider tiers** — Claude (Haiku/Sonnet/Opus), Codex (4o-mini/4o/o3), Gemini (Flash/Pro)
- **User override** — `@opus` or `@haiku` always takes priority over routing
- **Both features on by default** — just add an API key to activate
- **Zero overhead without key** — no extra calls, no latency

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
Three maintenance crons ship enabled by default:
- **Weekly cleanup** — remove one-shot crons, orphaned sessions, old temp files (Sunday 10:00)
- **Daily security audit** — check tokens, file permissions, disk usage, bot health (08:00)
- **Real-time memory consolidation** — module size enforcement (120-line limit) via hook system, no cron needed

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

On first run, Sygen creates a workspace at `~/.sygen/` with default tools, memory templates, and config.

## Configuration

All settings in `~/.sygen/config/config.json`. Key sections:

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

## Smart Routing

Automatically route messages to the optimal model and execution mode. A single cheap classifier call decides both the model tier and whether to run the task in the background. Both features are enabled by default — just add an API key to activate.

```json
{
  "routing": {
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
2. Classifier (cheap API call, ~100ms) rates complexity (light/medium/heavy) and execution mode (inline/background)
3. Message is routed to the matching model for the active provider
4. Long-running tasks are automatically delegated to background workers — the user can keep chatting

**Two independent features (both on by default):**
- `enabled` — model routing by complexity tier
- `auto_delegate` — automatic background task delegation

Either can be disabled independently:
```json
{ "routing": { "enabled": true, "auto_delegate": false, "api_key": "..." } }
```

**No API key = no routing.** Without `api_key`, both features are silently inactive. Add the key and everything works immediately.

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
pip install --upgrade sygen
```

## License

[MIT](LICENSE)
