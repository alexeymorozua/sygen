"""Agent observability: structured SQLite traces for cron, task, and webhook executions."""

from sygen_bot.observability.recorder import record_trace, read_traces

__all__ = ["record_trace", "read_traces"]
