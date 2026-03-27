# Sygen — Ideas & Future Features

Based on competitor research (OpenClaw, ClaudeClaw, Goose, Aider, Cursor, Devin — 15 projects analyzed, 2026-03-26).

## High Priority

### Multi-LLM Support
Per-chat/per-task model selection (Claude, GPT, Gemini, DeepSeek, local models).
- Reduces vendor lock-in + cost optimization
- OpenClaw, Goose, Aider all support this
- Complexity: MEDIUM

### Skill Marketplace
Community skill sharing + agent self-writing skills.
- OpenClaw's viral growth mechanism
- Agent creates its own new capabilities
- Complexity: HIGH

### PyPI Public Release
Publish Sygen to PyPI for `pip install sygen`.
- Register account on pypi.org
- Auto-update system already configured (version.py + UpdateObserver)
- Needs: PyPI account, decide on public vs private release

## Medium Priority

### Web Dashboard (Admin Panel)
React/Vue web UI for bot management instead of Telegram commands.
- Real-time logs, session history, token usage stats
- Config editing via UI (model, streaming, timeouts)
- Cron/webhook/sub-agent monitoring
- Auth via Tailscale or token
- Complexity: HIGH

### Cost Tracking
Per-chat/per-task cost tracking with limits.
- Data already available in session provider buckets (total_cost_usd, total_tokens)
- Need: aggregation, reporting command, optional limits
- Complexity: LOW (quick win!)

### AutoMemory Consolidation
Automatic memory cleanup and consolidation.
- Memory grows uncontrolled — needs automatic optimization
- Inspired by: Claude Code AutoDream
- Complexity: MEDIUM

### Upstream Monitoring
Weekly cron to check Ductor releases and notify about new features.
- Compare upstream tags with local version
- Summary of changes worth cherry-picking

### Sandbox Execution
Isolated code execution (bubblewrap / containers).
- OS-level sandboxing, sub-10ms cold starts
- Inspired by: ClaudeClaw
- Complexity: HIGH

## Low Priority / Ideas

### Discord Channel
Add Discord as a messaging transport.
- Expands audience, especially dev/gaming community
- Complexity: MEDIUM

### Plugin System
Allow users to drop custom tools into a `plugins/` directory with auto-discovery.

## Implemented

| Feature | Date | Details |
|---------|------|---------|
| MCP Integration | 2026-03-27 | Native client in `sygen_bot/mcp/` — MCPClient, MCPManager, ToolRouter, `/mcp` command, 52 tests |
| CI/CD | 2026-03-27 | GitHub Actions on push/PR, pytest on Python 3.11/3.12/3.13, 3400+ tests |
| Issue #75 Fix | 2026-03-27 | Cancel orphaned asyncio Tasks in cron reschedule — prevents double job execution |
| Multi-Model Routing | 2026-03-27 | Auto model selection by complexity via API classifier (Anthropic/OpenAI/Google). Optional, off by default. `sygen_bot/routing/`, 28 tests |

## Evaluated & Rejected

| Feature | Why rejected | Date |
|---------|-------------|------|
| Verbose Levels (`/verbose 0/1/2`) | Already covered by core: `reaction_style` (off/seen/detailed) + tool names + status tags in streaming | 2026-03-27 |
| Conversation Export | History already available in Telegram. Parsing 3 providers (Claude/Codex/Gemini) not worth the effort | 2026-03-27 |
| WhatsApp Channel | Official API is paid ($0.005-0.08/msg), 24h window limit, no message editing (kills streaming), no inline buttons (max 3 reply buttons), no forums/topics. Unofficial libs get banned. Not worth it for personal use | 2026-03-27 |
| Multi-Model Routing (rule-based) | Rule-based/keyword approaches are unreliable. CLI subprocess startup adds 3-5 sec if using CLI for classification. Solved via optional API classifier instead (see Implemented) | 2026-03-27 |
| Additional Providers (DeepSeek, Ollama) | Three providers (Claude/Codex/Gemini) are sufficient. Each new provider needs ~500 LOC CLI wrapper. No demand yet | 2026-03-27 |
