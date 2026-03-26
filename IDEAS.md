# Sygen — Ideas & Future Features

## High Priority

### Web Dashboard (Admin Panel)
React/Vue web UI for bot management instead of Telegram commands.
- Real-time logs, session history, token usage stats
- Config editing via UI (model, streaming, timeouts)
- Cron/webhook/sub-agent monitoring
- Auth via Tailscale or token
- Inspired by: ClaudeClaw web dashboard

## Medium Priority

### Upstream Monitoring
Weekly cron to check Ductor releases and notify about new features.
- Compare upstream tags with local version
- Summary of changes worth cherry-picking

### Verbose Levels Command
`/verbose 0|1|2` per-user command to control streaming detail:
- 0: final result only
- 1: tool names + status tags (current default)
- 2: tool names + parameters (`Read → config.json`, `Shell → git status`)
- Inspired by: claude-code-telegram

## Low Priority / Ideas

### Plugin System
Allow users to drop custom tools into a `plugins/` directory with auto-discovery.

### Multi-Model Routing
Route simple questions to cheaper models (Haiku), complex tasks to Opus.
Cost optimization without quality loss.

### Conversation Export
Export chat history to Markdown/PDF for archiving or sharing.
