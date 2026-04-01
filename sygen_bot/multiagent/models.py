"""Data models for multi-agent configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel

from sygen_bot.config import (
    AgentConfig,
    ApiConfig,
    CleanupConfig,
    CLIParametersConfig,
    DockerConfig,
    HeartbeatConfig,
    MatrixConfig,
    MCPConfig,
    StreamingConfig,
    WebhookConfig,
)


class SubAgentConfig(BaseModel):
    """Minimal sub-agent definition from agents.json.

    Only ``name`` is strictly required. Telegram agents need ``telegram_token``
    and ``allowed_user_ids``; Matrix agents need ``matrix`` config.
    All other fields are optional and inherit from the main agent config.
    """

    name: str
    transport: str = "telegram"  # "telegram" | "matrix"

    # Telegram credentials (required when transport=telegram)
    telegram_token: str = ""
    allowed_user_ids: list[int] | None = None
    allowed_group_ids: list[int] | None = None

    # Matrix credentials (required when transport=matrix)
    matrix: MatrixConfig | None = None

    # Group behaviour
    group_mention_only: bool | None = None

    # Optional overrides — inherit from main agent if None
    provider: str | None = None
    model: str | None = None
    log_level: str | None = None
    idle_timeout_minutes: int | None = None
    session_age_warning_hours: int | None = None
    daily_reset_hour: int | None = None
    daily_reset_enabled: bool | None = None
    max_budget_usd: float | None = None
    max_turns: int | None = None
    max_session_messages: int | None = None
    permission_mode: str | None = None
    cli_timeout: float | None = None
    reasoning_effort: str | None = None
    file_access: str | None = None
    streaming: StreamingConfig | None = None
    docker: DockerConfig | None = None
    heartbeat: HeartbeatConfig | None = None
    cleanup: CleanupConfig | None = None
    webhooks: WebhookConfig | None = None
    api: ApiConfig | None = None
    cli_parameters: CLIParametersConfig | None = None
    mcp: MCPConfig | None = None
    user_timezone: str | None = None


_log = logging.getLogger(__name__)


def merge_sub_agent_config(
    main: AgentConfig,
    sub: SubAgentConfig,
    agent_home: Path,
) -> AgentConfig:
    """Create a full AgentConfig by merging main config with sub-agent overrides.

    Merge order (later wins):
      1. main agent defaults
      2. sub-agent's own ``config/config.json`` (if present)
      3. ``agents.json`` explicit overrides (non-None fields)

    ``switch_model()`` keeps ``agents.json`` up-to-date when the user changes
    model/provider/reasoning_effort in a sub-agent chat, so no extra config
    layer is needed.
    """
    base = main.model_dump()

    # Sub-agent's own config/config.json (layer 2)
    local_config = agent_home / "config" / "config.json"
    if local_config.is_file():
        try:
            local_data = json.loads(local_config.read_text(encoding="utf-8"))
            if isinstance(local_data, dict):
                from sygen_bot.config import deep_merge_config

                base, _ = deep_merge_config(local_data, base)
                _log.debug("Merged sub-agent local config from %s", local_config)
        except (json.JSONDecodeError, OSError):
            _log.warning("Failed to read sub-agent config: %s", local_config)

    # agents.json explicit overrides (non-None fields win)
    overrides = sub.model_dump(exclude_none=True, exclude={"name"})
    base.update(overrides)

    base["sygen_home"] = str(agent_home)
    base["transport"] = sub.transport
    base["telegram_token"] = sub.telegram_token
    base["allowed_user_ids"] = sub.allowed_user_ids or []
    base["allowed_group_ids"] = sub.allowed_group_ids or []
    if sub.matrix is not None:
        base["matrix"] = sub.matrix.model_dump()

    # Sub-agents don't need the user-facing API server (they use InterAgentBus).
    # Disable it unless the sub-agent explicitly provides an api config.
    if sub.api is None:
        base.setdefault("api", {})["enabled"] = False

    return AgentConfig(**base)
