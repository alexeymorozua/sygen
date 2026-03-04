# text/

Shared user-facing response text helpers used across bot and orchestrator layers.

## Files

- `text/response_format.py`: formatter helpers, status/error text builders, startup/recovery text

## Public API (`response_format.py`)

- `SEP`: shared section separator
- `fmt(*blocks)`: join non-empty blocks with blank lines
- `classify_cli_error(raw)`
- `session_error_text(model, cli_detail="")`
- `new_session_text(provider)`
- `stop_text(killed, provider)`
- `timeout_warning_text(remaining)`
- `timeout_extended_text(extension, remaining_ext)`
- `timeout_result_text(elapsed, configured)`
- `startup_notification_text(kind)`
- `recovery_notification_text(kind, prompt_preview, session_name="")`

## Integration points

- `bot/handlers.py`: `/new`, `/stop`
- `bot/app.py`: help/info/restart and various user-facing blocks
- `bot/file_browser.py`, `bot/welcome.py`
- `orchestrator/commands.py`: `/status`, `/memory`, `/diagnose`, `/upgrade`, etc.
- `orchestrator/flows.py`: session error rendering and timeout-facing text
- `orchestrator/selectors/cron_selector.py`: cron selector text blocks
- `bot/message_dispatch.py`: maps timeout status labels when emitted

## Behavior notes

- error hints are pattern-based and intentionally conservative
- session error text explicitly states that session context is preserved
- timeout warning/extension helpers exist, but visible status labels depend on emitted system-status events
