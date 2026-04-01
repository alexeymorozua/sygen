"""Shared fixtures for workflow engine tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from sygen_bot.workflow.models import (
    StepDefinition,
    StepType,
    TriggerConfig,
    WorkflowDefinition,
)
from sygen_bot.workflow.registry import WorkflowRegistry
from sygen_bot.workflow.engine import WorkflowEngine


SAMPLE_YAML = textwrap.dedent("""\
    id: test_workflow
    name: Test Workflow
    trigger:
      manual: true
    variables:
      greeting: hello
    steps:
      - id: step1
        type: ask_agent
        agent: helper
        prompt: "Say $greeting"
        timeout: 60
      - id: step2
        type: notify
        message: "Result: $steps.step1.output"
      - id: step3
        type: wait_for_reply
        prompt: "Approve?"
      - id: step4
        type: condition
        if: "'yes' in '$steps.step3.output'.lower()"
        then: done
        else: step1
      - id: done
        type: notify
        message: "Done!"
""")


@pytest.fixture()
def sample_yaml() -> str:
    return SAMPLE_YAML


@pytest.fixture()
def sample_definition() -> WorkflowDefinition:
    raw = yaml.safe_load(SAMPLE_YAML)
    return WorkflowDefinition.model_validate(raw)


@pytest.fixture()
def tmp_workflows_dir(tmp_path: Path) -> Path:
    d = tmp_path / "workflows"
    d.mkdir()
    (d / "test_workflow.yaml").write_text(SAMPLE_YAML, encoding="utf-8")
    return d


@pytest.fixture()
def registry(tmp_path: Path, tmp_workflows_dir: Path) -> WorkflowRegistry:
    runs_path = tmp_path / "runs.json"
    return WorkflowRegistry(tmp_workflows_dir, runs_path)


@pytest.fixture()
def mock_notify() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_ask_agent() -> AsyncMock:
    return AsyncMock(return_value="Agent response")


@pytest.fixture()
def engine(
    registry: WorkflowRegistry,
    mock_notify: AsyncMock,
    mock_ask_agent: AsyncMock,
) -> WorkflowEngine:
    return WorkflowEngine(
        registry,
        notify_callback=mock_notify,
        ask_agent_fn=mock_ask_agent,
    )
