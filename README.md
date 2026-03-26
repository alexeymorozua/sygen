# Sygen

AI assistant framework with multi-agent orchestration, background tasks, and persistent memory.

Private fork of [Ductor](https://github.com/PleasePrompto/ductor), developed independently for custom needs.

## Key Features

- **Multi-agent system** — supervisor + sub-agents with shared knowledge
- **Background task delegation** — delegate work, keep chatting, get results back
- **Persistent memory** — per-agent and shared memory in plain Markdown
- **Multi-transport** — Telegram (primary), Matrix
- **Multi-provider** — Claude Code, Codex CLI, Gemini CLI
- **Cron & webhooks** — built-in scheduler and webhook server
- **Named sessions** — multiple isolated contexts per chat
- **Docker sandbox** — optional secure execution environment

## Quick Start

```bash
pip install -e .
sygen
```

## Upstream Sync

Original Ductor is tracked as `upstream` remote:

```bash
git fetch upstream
git log upstream/main --oneline    # review changes
git cherry-pick <commit>           # pick what you need
```

## License

[MIT](LICENSE)
