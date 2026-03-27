# Sygen — Roadmap

All planned features have been implemented or covered by existing systems.
New ideas will be added as they emerge.

## Implemented

| Feature | Date | Details |
|---------|------|---------|
| Full Rebrand | 2026-03-27 | Complete rebrand across entire codebase (213 files), no backward compat |
| PyPI Release | 2026-03-27 | `pip install sygen`, auto-publish on GitHub release |
| ClawHub Skill Marketplace | 2026-03-27 | Browse/install community skills with security scanning (static + VirusTotal) |
| Multi-Model Routing | 2026-03-27 | Auto model selection by task complexity via API classifier |
| MCP Integration | 2026-03-27 | Native MCP client — MCPClient, MCPManager, ToolRouter, `/mcp` command |
| CI/CD | 2026-03-27 | GitHub Actions, pytest on Python 3.11/3.12/3.13, 3500+ tests |
| Cost Tracking | core | Per-session cost/token tracking, `/status` display, budget limits (`max_budget_usd`) |
| Upstream Monitoring | core | PyPI version polling (hourly), auto-upgrade with retry, GitHub changelog |
| Sandbox Execution | core | Docker-based isolation, auto-build, mount strategy, extras system, host fallback |
| Memory Consolidation | 2026-03-27 | Real-time module size enforcement (120-line limit) via hook system, replaced monthly cron tasks |
| Cron Results Buffer | 2026-03-27 | Per-job file buffer in `cron_results/`, agent sees latest cron output in context, auto-clear on `/new` |
| Skill/Plugin System | core | Workspace skills with auto-sync, ClawHub marketplace, SKILL.md format |
