# Sygen

**AI assistant framework with multi-agent orchestration, background tasks, and persistent memory.**

Sygen routes chat input to provider CLIs (Claude, Codex, Gemini), streams responses back via Telegram or Matrix, persists session state, and runs cron, heartbeat, webhook, and cleanup automation in-process. It also supports a direct WebSocket API transport with authenticated file upload/download.

---

## Feature Highlights

- **Multi-provider routing** -- Claude Code, Codex, and Gemini CLI backends with automatic stream parsing and normalization.
- **Telegram and Matrix transports** -- Full bot integration with middleware, topic routing, streaming dispatch, and reaction buttons.
- **Multi-agent orchestration** -- Supervisor-managed sub-agents with inter-agent bus, shared knowledge sync, and independent workspaces.
- **Background task delegation** -- Long-running tasks execute in separate processes while the conversation continues.
- **Persistent memory** -- Session state, named sessions, and durable memory across restarts.
- **Cron, webhooks, and heartbeat** -- In-process automation observers for scheduled jobs, external triggers, and health monitoring.
- **WebSocket API** -- Direct ingress via `/ws` with HTTP file endpoints for programmatic access.
- **Skill system and marketplace** -- Extensible skill architecture with sync and discovery.
- **Advanced RAG pipeline** -- BM25 + vector hybrid search with ColBERT v2 reranking, query expansion, and LRU cache. 50+ languages, fully local.
- **Sandboxed execution** -- Optional Docker sandbox for safe command execution.

---

## Quick Start

### Install

=== "pipx (recommended)"

    ```bash
    pipx install sygen
    ```

=== "pip"

    ```bash
    pip install sygen
    ```

=== "From source"

    ```bash
    git clone https://github.com/alexeymorozua/sygen.git
    cd sygen
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    ```

### Run the setup wizard

```bash
sygen onboarding
```

The wizard walks you through provider authentication, transport configuration (Telegram or Matrix), and optional Docker sandbox setup.

### Start the bot

```bash
sygen
```

---

## Quick Links

| Section | Description |
|---|---|
| [Installation](installation.md) | Full install guide with requirements and options |
| [Developer Quickstart](developer_quickstart.md) | Shortest path for contributors |
| [Configuration](config.md) | Config schema, merge behavior, hot-reload |
| [Architecture](architecture.md) | Startup, routing, streaming, callbacks |
| [System Overview](system_overview.md) | End-to-end mental model |
| [Modules](modules/orchestrator.md) | Detailed module documentation |

---

## Requirements

- Python 3.11+
- At least one authenticated provider CLI (Claude Code, Codex, or Gemini)
- Telegram bot token or Matrix credentials
- Docker (optional, recommended for sandboxing)
