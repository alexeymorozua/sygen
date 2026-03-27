# Sygen — Roadmap

New ideas will be added as they emerge.

## Implemented

| Feature | Version | Details |
|---------|---------|---------|
| Buffered Streaming | 1.0.9 | `streaming.buffered` — reactions update in real-time (👀→🤔→⚙️→📦→✅) while text arrives as one complete message |
| Built-in File Cleanup | 1.0.8 | CleanupObserver — daily auto-cleanup of media files, output, tasks, cron results. Replaces per-agent cron jobs |
| Agent Observability | 1.0.2 | SQLite-based execution traces for cron, tasks, webhooks. `/logs` command with filtering. Auto-rotation (30 days / 1000 entries) |
| Silent Cron Output | 1.0.2 | `[SILENT]` marker — cron/webhook tasks can suppress delivery when nothing to report. Traces still recorded |
| Mobile-Friendly Tables | 1.0.2 | Framework-level conversion of Markdown tables to grouped lists for Telegram readability |
| Full Rebrand | 1.0.0 | Complete rebrand across entire codebase (213 files), no backward compat |
| PyPI Release | 1.0.0 | `pip install sygen`, auto-publish on GitHub release |
| ClawHub Skill Marketplace | 1.0.0 | Browse/install community skills with security scanning (static + VirusTotal) |
| MCP Integration | 1.0.0 | Native MCP client — MCPClient, MCPManager, ToolRouter, `/mcp` command |
| CI/CD | 1.0.0 | GitHub Actions, pytest on Python 3.11/3.12/3.13, 3500+ tests |
| Cost Tracking | core | Per-session cost/token tracking, `/status` display, budget limits (`max_budget_usd`) |
| Upstream Monitoring | core | PyPI version polling (hourly), auto-upgrade with retry, GitHub changelog |
| Sandbox Execution | core | Docker-based isolation, auto-build, mount strategy, extras system, host fallback |
| Memory Consolidation | 1.0.0 | Real-time module size enforcement (120-line limit) via hook system, replaced monthly cron tasks |
| Cron Results Buffer | 1.0.0 | Per-job file buffer in `cron_results/`, agent sees latest cron output in context, auto-clear on `/new` |
| Skill/Plugin System | core | Workspace skills with auto-sync, ClawHub marketplace, SKILL.md format |
