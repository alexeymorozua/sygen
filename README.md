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

## Upstream Sync

Forked from [Ductor](https://github.com/PleasePrompto/ductor). Original tracked as `upstream` remote:

```bash
git fetch upstream
git log upstream/main --oneline    # review changes
git cherry-pick <commit>           # pick what you need
```

## License

[MIT](LICENSE)
