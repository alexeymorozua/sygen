"""Tests for workflow data models."""

from __future__ import annotations

import pytest
import yaml

from sygen_bot.workflow.models import (
    ErrorAction,
    StepDefinition,
    StepRun,
    StepStatus,
    StepType,
    TriggerConfig,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
)


class TestStepTypeEnum:
    def test_enum_values(self):
        assert StepType.ASK_AGENT == "ask_agent"
        assert StepType.NOTIFY == "notify"
        assert StepType.WAIT_FOR_REPLY == "wait_for_reply"
        assert StepType.CONDITION == "condition"
        assert StepType.PARALLEL == "parallel"
        assert StepType.SCRIPT == "script"

    def test_all_members(self):
        names = {m.value for m in StepType}
        assert names == {
            "ask_agent", "notify", "wait_for_reply",
            "condition", "parallel", "script",
        }


class TestWorkflowDefinitionFromYaml:
    def test_from_yaml_dict(self, sample_yaml: str):
        raw = yaml.safe_load(sample_yaml)
        defn = WorkflowDefinition.model_validate(raw)
        assert defn.id == "test_workflow"
        assert defn.name == "Test Workflow"
        assert defn.variables == {"greeting": "hello"}
        assert len(defn.steps) == 5
        assert defn.steps[0].type == StepType.ASK_AGENT
        assert defn.steps[0].agent == "helper"
        assert defn.steps[3].type == StepType.CONDITION

    def test_step_types_parsed(self, sample_yaml: str):
        raw = yaml.safe_load(sample_yaml)
        defn = WorkflowDefinition.model_validate(raw)
        types = [s.type for s in defn.steps]
        assert types == [
            StepType.ASK_AGENT,
            StepType.NOTIFY,
            StepType.WAIT_FOR_REPLY,
            StepType.CONDITION,
            StepType.NOTIFY,
        ]


class TestStepDefinitionAliasFields:
    def test_if_alias(self):
        step = StepDefinition.model_validate({
            "id": "cond1",
            "type": "condition",
            "if": "'a' == 'a'",
            "then": "next",
            "else": "other",
        })
        assert step.if_expr == "'a' == 'a'"
        assert step.then == "next"
        assert step.else_ == "other"

    def test_if_expr_direct(self):
        step = StepDefinition(
            id="cond2",
            type=StepType.CONDITION,
            if_expr="True",
            then="x",
            else_="y",
        )
        assert step.if_expr == "True"


class TestWorkflowRunDefaults:
    def test_defaults(self):
        run = WorkflowRun(run_id="abc", workflow_id="wf1")
        assert run.status == WorkflowRunStatus.PENDING
        assert run.variables == {}
        assert run.step_runs == {}
        assert run.current_step_id == ""
        assert run.chat_id == 0
        assert run.topic_id is None
        assert run.transport == "tg"
        assert run.parent_agent == "main"
        assert run.error == ""
        assert run.wait_step_id == ""


class TestStepRunStatusTransitions:
    def test_default_pending(self):
        sr = StepRun(step_id="s1")
        assert sr.status == StepStatus.PENDING

    def test_can_transition(self):
        sr = StepRun(step_id="s1")
        sr.status = StepStatus.RUNNING
        assert sr.status == StepStatus.RUNNING
        sr.status = StepStatus.COMPLETED
        assert sr.status == StepStatus.COMPLETED

    def test_failed_with_error(self):
        sr = StepRun(step_id="s1")
        sr.status = StepStatus.FAILED
        sr.error = "something broke"
        assert sr.status == StepStatus.FAILED
        assert sr.error == "something broke"


class TestInvalidStepType:
    def test_invalid_type_raises(self):
        with pytest.raises(Exception):
            StepDefinition.model_validate({
                "id": "bad",
                "type": "nonexistent_type",
            })
