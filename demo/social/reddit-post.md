# Sygen v1.1.9 -- Self-hosted AI assistant with multi-agent orchestration, local RAG, and 3000+ integrations

**TL;DR:** Sygen is a self-hosted AI assistant framework. You deploy it on your own server, connect it to Telegram (or Matrix), and get a persistent AI assistant with memory, scheduled tasks, sub-agents, and local RAG -- no cloud dependency.

## What it does

- **Telegram/Matrix-first**: Your AI lives in your messenger. No separate app, no web UI required.
- **Multi-agent orchestration**: Spin up sub-agents that work autonomously. Delegate tasks, get results back. Each agent has its own chat, memory, and workspace.
- **Local RAG pipeline**: Index your documents (Markdown, TXT, YAML, 50+ languages) with ColBERT v2. Answers are grounded in your data. Runs entirely on your hardware.
- **13,000+ skills via ClawHub**: Install community skills with one command. Code generation, research, translation, automation -- the catalog keeps growing.
- **MCP native**: 3,000+ tool integrations out of the box (Model Context Protocol). Connect to databases, APIs, SaaS tools without writing glue code.
- **Persistent memory**: Remembers your preferences, project context, and facts across sessions. No re-explaining.
- **Cron tasks**: Schedule recurring AI work -- daily summaries, monitoring checks, report generation.
- **Webhooks**: Trigger AI workflows from external events.

## Self-hosted, zero cloud

Everything runs on your machine. Your data never leaves your server. Supports Claude Code (Anthropic), Codex CLI (OpenAI), and Gemini CLI (Google) as AI backends.

## Quick start

```bash
pip install sygen
sygen onboarding
# Edit ~/.sygen/config/config.json with your bot token
sygen
```

## Links

- GitHub: [REPO_URL]
- Docs: [DOCS_URL]
- Demo recording: [ASCIINEMA_URL]

## Tech stack

Python 3.11+, asyncio, aiogram, ColBERT v2 (RAG), MCP protocol, SQLite (traces).

---

Happy to answer questions. Feedback welcome -- especially on the multi-agent workflow and RAG pipeline.
