# Developer Quickstart

Fast onboarding path for contributors and junior devs.

## 1) Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional for full runtime validation:

- install/auth at least one provider CLI (`claude`, `codex`, `gemini`)
- set up a messaging transport:
  - **Telegram**: bot token from @BotFather + user ID (`allowed_user_ids`)
  - **Matrix**: account on any homeserver (homeserver URL, user ID, password, `allowed_users`)
- for Telegram group support, also set `allowed_group_ids`

## 2) Run the bot

```bash
sygen
```

First run starts onboarding and writes config to `~/.sygen/config/config.json`.

Primary runtime files/directories:

- `~/.sygen/sessions.json`
- `~/.sygen/named_sessions.json`
- `~/.sygen/tasks.json`
- `~/.sygen/chat_activity.json`
- `~/.sygen/cron_jobs.json`
- `~/.sygen/webhooks.json`
- `~/.sygen/startup_state.json`
- `~/.sygen/inflight_turns.json`
- `~/.sygen/SHAREDMEMORY.md`
- `~/.sygen/agents.json`
- `~/.sygen/agents/`
- `~/.sygen/workspace/`
- `~/.sygen/logs/agent.log`

## 3) Quality gates

```bash
pytest
ruff format .
ruff check .
mypy sygen_bot
```

Expected: zero warnings, zero errors.

## 4) Core mental model

```text
Telegram / Matrix / API input
  -> ingress layer (TelegramBot / MatrixBot / ApiServer)
  -> orchestrator flow
  -> provider CLI subprocess
  -> response delivery (transport-specific)

background/async results
  -> Envelope adapters
  -> MessageBus
  -> optional session injection
  -> transport delivery (Telegram or Matrix)
```

## 5) Read order in code

Entry + command layer:

- `sygen_bot/__main__.py`
- `sygen_bot/cli_commands/`

Runtime hot path:

- `sygen_bot/multiagent/supervisor.py`
- `sygen_bot/messenger/telegram/app.py`
- `sygen_bot/messenger/telegram/startup.py`
- `sygen_bot/orchestrator/core.py`
- `sygen_bot/orchestrator/lifecycle.py`
- `sygen_bot/orchestrator/flows.py`

Delivery/task/session core:

- `sygen_bot/bus/`
- `sygen_bot/session/manager.py`
- `sygen_bot/tasks/hub.py`
- `sygen_bot/tasks/registry.py`

Provider/API/workspace core:

- `sygen_bot/cli/service.py` + provider wrappers
- `sygen_bot/api/server.py`
- `sygen_bot/workspace/init.py`
- `sygen_bot/workspace/rules_selector.py`
- `sygen_bot/workspace/skill_sync.py`

## 6) Common debug paths

If command behavior is wrong:

1. `sygen_bot/__main__.py`
2. `sygen_bot/cli_commands/*`

If Telegram routing is wrong:

1. `sygen_bot/messenger/telegram/middleware.py`
2. `sygen_bot/messenger/telegram/app.py`
3. `sygen_bot/orchestrator/commands.py`
4. `sygen_bot/orchestrator/flows.py`

If Matrix routing is wrong:

1. `sygen_bot/messenger/matrix/bot.py`
2. `sygen_bot/messenger/matrix/transport.py`
3. `sygen_bot/orchestrator/flows.py`

If background results look wrong:

1. `sygen_bot/bus/adapters.py`
2. `sygen_bot/bus/bus.py`
3. `sygen_bot/messenger/telegram/transport.py` (or `sygen_bot/messenger/matrix/transport.py`)

If tasks are wrong:

1. `sygen_bot/tasks/hub.py`
2. `sygen_bot/tasks/registry.py`
3. `sygen_bot/multiagent/internal_api.py`
4. `sygen_bot/_home_defaults/workspace/tools/task_tools/*.py`

If API is wrong:

1. `sygen_bot/api/server.py`
2. `sygen_bot/orchestrator/lifecycle.py` (API startup wiring)
3. `sygen_bot/files/*` (allowed roots, MIME, prompt building)

## 7) Behavior details to remember

- `/stop` and `/stop_all` are pre-routing abort paths in middleware/bot.
- `/new` resets only active provider bucket for the active `SessionKey`.
- session identity is transport-aware: `SessionKey(transport, chat_id, topic_id)`.
- `/model` inside a topic updates only that topic session (not global config).
- task tools now support permanent single-task removal via `delete_task.py` (`/tasks/delete`).
- task routing is topic-aware via `thread_id` and `SYGEN_TOPIC_ID`.
- API auth accepts optional `channel_id` for per-channel session isolation.
- startup recovery uses `inflight_turns.json` + recovered named sessions.
- auth allowlists (`allowed_user_ids`, `allowed_group_ids`) are hot-reloadable.
- `sygen agents add` is a Telegram-focused scaffold; Matrix sub-agents are supported through `agents.json` or the bundled agent tool scripts.

Continue with `docs/system_overview.md` and `docs/architecture.md` for complete runtime detail.
