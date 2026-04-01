# Sygen — Roadmap

New ideas will be added as they emerge.

## Implemented

| Feature | Version | Details |
|---------|---------|---------|
| Advanced RAG Pipeline | 1.1.9 | Hybrid BM25 + vector search with RRF fusion, ColBERT v2 multilingual reranking, smart chunking, query expansion, multi-source indexing, LRU cache. Fully local, no API keys. [Docs](docs/RAG.md) |
| Workflow Engine | 1.1.8 | YAML-defined multi-agent pipelines with conditions, retries, fallbacks, parallel execution, wait_for_reply. `/workflow` command, HTTP API, filesystem observer. [Docs](docs/WORKFLOW.md) |
| MCP JSON Array Fix | 1.1.8 | Fixed `_parse_response()` crash when Claude CLI with MCP returns a JSON array instead of a single object |
| Codebase Review Fixes | 1.1.7 | Atomic config swap, `fcntl.flock` PID lock, `threading.Lock` for CronManager/Gemini, stable `hashlib.md5` chat IDs, Matrix parity fixes, ChromaDB upsert reindex |
| Unified /upgrade + Emoji Fix | 1.0.12 | `/upgrade` uses pip pipeline with changelog for all install modes. Fixed reactions: valid Telegram emojis. Post-restart shows changelog |
| Memory Observer | 1.0.10 | MemoryObserver — mechanical memory maintenance in core: dedup, line limits, orphan session cleanup, one-shot cron removal |
| Buffered Streaming | 1.0.9 | `streaming.buffered` — reactions update in real-time while text arrives as one complete message |
| Built-in File Cleanup | 1.0.8 | CleanupObserver — daily auto-cleanup of media files, output, tasks, cron results |
| Agent Observability | 1.0.2 | SQLite-based execution traces for cron, tasks, webhooks. `/logs` command with filtering. Auto-rotation |
| Silent Cron Output | 1.0.2 | `[SILENT]` marker — cron/webhook tasks can suppress delivery when nothing to report |
| Mobile-Friendly Tables | 1.0.2 | Framework-level conversion of Markdown tables to grouped lists for Telegram readability |
| Full Rebrand + PyPI | 1.0.0 | Complete rebrand (213 files), `pip install sygen`, auto-publish on GitHub release |
| ClawHub Skill Marketplace | 1.0.0 | Browse/install community skills with security scanning (static + VirusTotal) |
| MCP Integration | 1.0.0 | Native MCP client — MCPClient, MCPManager, ToolRouter, `/mcp` command |
| CI/CD | 1.0.0 | GitHub Actions, pytest on Python 3.11/3.12/3.13, 3700+ tests |
| Cost Tracking | core | Per-session cost/token tracking, `/status` display, budget limits (`max_budget_usd`) |
| Upstream Monitoring | core | PyPI version polling (hourly), auto-upgrade with retry, GitHub changelog |
| Sandbox Execution | core | Docker-based isolation, auto-build, mount strategy, extras system, host fallback |
| Memory Consolidation | 1.0.0 | Real-time module size enforcement (120-line limit) via hook system |
| Cron Results Buffer | 1.0.0 | Per-job file buffer in `cron_results/`, agent sees latest cron output in context |
| Skill/Plugin System | core | Workspace skills with auto-sync, ClawHub marketplace, SKILL.md format |

## Planned

| Feature | Priority | Details |
|---------|----------|---------|
| ~~Advanced RAG Pipelines~~ | ~~High~~ | ✅ Implemented in 1.1.9 |
| Workflow Triggers | Medium | Cron-based and webhook-triggered workflow execution (currently manual only) |
| Workflow `script` Step Type | Medium | Execute shell commands or Python scripts as workflow steps |
| A2A Protocol | Medium | Google Agent-to-Agent protocol support for cross-framework agent communication |
| Streaming Workflows | Low | Real-time step output streaming to chat during workflow execution |
| Workflow Templates | Low | Pre-built workflow templates for common patterns (research, code review, content creation) |
