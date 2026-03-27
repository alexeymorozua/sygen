# Sygen — Roadmap

## Planned

### AutoMemory Consolidation
Programmatic memory deduplication, contradiction detection, and staleness pruning. Cron-based cleanup tasks exist; goal is automated algorithms in core.

### Web Dashboard
Admin panel for bot management — logs, config editing, cron/webhook monitoring.

### Discord Channel
Discord as an additional messaging transport.

### Plugin System
Drop-in custom tools with auto-discovery from a `plugins/` directory.

## Implemented

| Feature | Date | Details |
|---------|------|---------|
| Full Rebrand | 2026-03-27 | Complete ductor → sygen across entire codebase (213 files), no backward compat |
| PyPI Release | 2026-03-27 | `pip install sygen`, auto-publish on GitHub release |
| ClawHub Skill Marketplace | 2026-03-27 | Browse/install community skills with security scanning (static + VirusTotal) |
| Multi-Model Routing | 2026-03-27 | Auto model selection by task complexity via API classifier |
| MCP Integration | 2026-03-27 | Native MCP client — MCPClient, MCPManager, ToolRouter, `/mcp` command |
| CI/CD | 2026-03-27 | GitHub Actions, pytest on Python 3.11/3.12/3.13, 3500+ tests |
| Cost Tracking | core | Per-session cost/token tracking, `/status` display, budget limits (`max_budget_usd`) |
| Upstream Monitoring | core | PyPI version polling (hourly), auto-upgrade with retry, GitHub changelog |
| Sandbox Execution | core | Docker-based isolation, auto-build, mount strategy, extras system, host fallback |
