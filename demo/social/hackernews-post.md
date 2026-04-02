# Show HN: Sygen -- Self-hosted AI assistant with multi-agent orchestration and local RAG

## Title (for HN submission)

Show HN: Sygen -- Self-hosted multi-agent AI assistant for Telegram with local RAG

## URL

[REPO_URL]

## Text (if no URL, or for the comment)

Sygen is a self-hosted AI assistant framework that runs in Telegram (and Matrix). I built it because I wanted a persistent AI that lives in my messenger, remembers context, and can run background tasks without depending on any cloud service.

Key features:

- Multi-agent system: create sub-agents that work in parallel, each with their own Telegram bot, memory, and workspace. Delegate complex tasks and get results back.

- Local RAG with ColBERT v2: index your documents (Markdown, TXT, YAML) in 50+ languages. Answers are grounded in your data, running entirely on your hardware.

- 13,000+ installable skills via ClawHub -- community-contributed capabilities you can add with one command.

- MCP native: 3,000+ tool integrations through Model Context Protocol. Databases, APIs, SaaS -- no custom glue code.

- Persistent memory, cron tasks, webhooks, and a full workspace the AI can use for file operations.

Everything runs on your server. Supports Claude Code, Codex CLI, and Gemini CLI as backends. Python, pip install, done.

Quick start:

```
pip install sygen
sygen onboarding
sygen
```

GitHub: [REPO_URL]

Would love feedback on the multi-agent architecture and RAG pipeline design.
