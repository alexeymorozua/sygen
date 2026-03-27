"""Trace recorder: writes and reads structured JSON trace files."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sygen_bot.observability.cleanup import run_cleanup

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Trace:
    id: str
    type: str  # "cron" | "task" | "webhook"
    name: str
    started: str
    finished: str
    duration_sec: float
    status: str  # "ok" | "error" | "timeout" | "aborted"
    provider: str
    model: str
    error: str | None = None
    summary: str | None = None


def _traces_dir(logs_dir: Path) -> Path:
    return logs_dir / "traces"


def _normalize_status(raw_status: str) -> str:
    if raw_status in ("ok", "success"):
        return "ok"
    if "timeout" in raw_status:
        return "timeout"
    if raw_status == "aborted":
        return "aborted"
    if raw_status.startswith("error") or raw_status.startswith("skipped"):
        return "error"
    return "ok"


def record_trace(
    logs_dir: Path,
    *,
    trace_type: str,
    name: str,
    started: datetime,
    finished: datetime,
    duration_sec: float,
    status: str,
    provider: str,
    model: str,
    error: str | None = None,
    summary: str | None = None,
    retention_days: int = 30,
    max_files: int = 1000,
) -> None:
    normalized = _normalize_status(status)
    ts = started.strftime("%Y%m%d-%H%M%S")
    trace_id = f"{trace_type}-{name}-{ts}"
    trace = Trace(
        id=trace_id,
        type=trace_type,
        name=name,
        started=started.isoformat(),
        finished=finished.isoformat(),
        duration_sec=round(duration_sec, 1),
        status=normalized,
        provider=provider or "",
        model=model or "",
        error=error if normalized != "ok" else None,
        summary=(summary[:200] if summary else None),
    )

    traces = _traces_dir(logs_dir)
    traces.mkdir(parents=True, exist_ok=True)

    filename = f"{trace_type}-{name}-{ts}.json"
    path = traces / filename
    try:
        path.write_text(json.dumps(asdict(trace), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        logger.exception("Failed to write trace %s", filename)
        return

    try:
        run_cleanup(traces, retention_days=retention_days, max_files=max_files)
    except Exception:
        logger.exception("Trace cleanup failed")


def read_traces(
    logs_dir: Path,
    *,
    trace_type: str | None = None,
    name: str | None = None,
    errors_only: bool = False,
    since: datetime | None = None,
    limit: int = 10,
) -> list[Trace]:
    traces = _traces_dir(logs_dir)
    if not traces.is_dir():
        return []

    files = sorted(traces.glob("*.json"), key=lambda p: p.name, reverse=True)

    result: list[Trace] = []
    for f in files:
        if len(result) >= limit:
            break
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if trace_type and data.get("type") != trace_type:
            continue
        if name and data.get("name") != name:
            continue
        if errors_only and data.get("status") == "ok":
            continue
        if since:
            try:
                started = datetime.fromisoformat(data["started"])
                if started < since:
                    continue
            except (ValueError, KeyError):
                continue

        result.append(Trace(**data))

    return result
