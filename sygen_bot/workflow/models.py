"""Workflow engine data models.

Pydantic models for workflow definitions, step definitions,
and runtime state (runs).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ────────────────────────────────────────────────────────────


class StepType(str, Enum):
    ASK_AGENT = "ask_agent"
    NOTIFY = "notify"
    WAIT_FOR_REPLY = "wait_for_reply"
    CONDITION = "condition"
    PARALLEL = "parallel"
    SCRIPT = "script"


class ErrorAction(str, Enum):
    ABORT = "abort"
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Config helpers ───────────────────────────────────────────────────


class RetryConfig(BaseModel):
    max_attempts: int = 3
    delay_seconds: float = 30.0


class FallbackConfig(BaseModel):
    goto: str


# ── Step definition ──────────────────────────────────────────────────


class StepDefinition(BaseModel):
    """Single step inside a workflow definition."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: StepType
    agent: str = ""
    prompt: str = ""
    message: str = ""
    timeout: float = 3600.0
    on_error: ErrorAction = ErrorAction.ABORT
    retry: RetryConfig | None = None
    fallback: FallbackConfig | None = None
    goto: str = ""

    # condition fields
    if_expr: str = Field("", alias="if")
    then: str = ""
    else_: str = Field("", alias="else")

    # parallel sub-steps
    steps: list[StepDefinition] = []

    # provider overrides
    provider: str = ""
    model: str = ""
    new_session: bool = True


# ── Workflow definition ──────────────────────────────────────────────


class TriggerConfig(BaseModel):
    cron: str = ""
    manual: bool = True


class WorkflowDefinition(BaseModel):
    """Full workflow as loaded from a YAML file."""

    id: str
    name: str
    description: str = ""
    version: int = 1
    trigger: TriggerConfig
    variables: dict[str, Any] = {}
    steps: list[StepDefinition]


# ── Runtime state ────────────────────────────────────────────────────


class StepRun(BaseModel):
    """Runtime state for a single step execution."""

    step_id: str
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    attempt: int = 0


class WorkflowRun(BaseModel):
    """Runtime state for a single workflow execution."""

    run_id: str
    workflow_id: str
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    variables: dict[str, Any] = {}
    step_runs: dict[str, StepRun] = {}
    current_step_id: str = ""
    chat_id: int = 0
    topic_id: int | None = None
    transport: str = "tg"
    parent_agent: str = "main"
    created_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""
    wait_step_id: str = ""
