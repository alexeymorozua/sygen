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

### Multi-Model Routing
Route simple questions to cheaper models (Haiku), complex tasks to Opus.
Cost optimization without quality loss. ~1-2 hours to implement basic version.

## Already Implemented / Rejected

- ~~MCP Integration~~ — native MCP client implemented in sygen_bot/mcp/ (client, manager, tool_router, /mcp command)
- ~~Verbose Levels~~ — covered by core: reaction_style (off/seen/detailed) + tool names + status tags
- ~~Conversation Export~~ — not needed, history already in Telegram
- ~~WhatsApp Channel~~ — API платный, ограниченный (нет edit/streaming/кнопок), для личного use-case не оправдан
