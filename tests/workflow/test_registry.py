"""Tests for WorkflowRegistry."""

from __future__ import annotations

from pathlib import Path

from sygen_bot.workflow.models import WorkflowRunStatus
from sygen_bot.workflow.registry import WorkflowRegistry


class TestLoadDefinitions:
    def test_loads_yaml_files(self, registry: WorkflowRegistry):
        defs = registry.load_definitions()
        assert "test_workflow" in defs
        assert defs["test_workflow"].name == "Test Workflow"

    def test_get_definition(self, registry: WorkflowRegistry):
        defn = registry.get_definition("test_workflow")
        assert defn is not None
        assert len(defn.steps) == 5

    def test_missing_definition(self, registry: WorkflowRegistry):
        assert registry.get_definition("nonexistent") is None


class TestCreateRun:
    def test_generates_id(self, registry: WorkflowRegistry):
        run = registry.create_run("test_workflow", chat_id=123)
        assert run.run_id
        assert len(run.run_id) == 32
        assert run.workflow_id == "test_workflow"
        assert run.chat_id == 123

    def test_inherits_variables(self, registry: WorkflowRegistry):
        run = registry.create_run("test_workflow", chat_id=1)
        assert run.variables.get("greeting") == "hello"

    def test_variable_overrides(self, registry: WorkflowRegistry):
        run = registry.create_run(
            "test_workflow", chat_id=1,
            variable_overrides={"greeting": "hi", "extra": "val"},
        )
        assert run.variables["greeting"] == "hi"
        assert run.variables["extra"] == "val"


class TestUpdateAndGetRun:
    def test_update_and_get(self, registry: WorkflowRegistry):
        run = registry.create_run("test_workflow", chat_id=1)
        run.status = WorkflowRunStatus.RUNNING
        registry.update_run(run)
        fetched = registry.get_run(run.run_id)
        assert fetched is not None
        assert fetched.status == WorkflowRunStatus.RUNNING


class TestListRuns:
    def test_list_all(self, registry: WorkflowRegistry):
        registry.create_run("test_workflow", chat_id=1)
        registry.create_run("test_workflow", chat_id=2)
        assert len(registry.list_runs()) == 2

    def test_filter_by_status(self, registry: WorkflowRegistry):
        run = registry.create_run("test_workflow", chat_id=1)
        run.status = WorkflowRunStatus.RUNNING
        registry.update_run(run)
        registry.create_run("test_workflow", chat_id=2)

        running = registry.list_runs(status_filter=WorkflowRunStatus.RUNNING)
        assert len(running) == 1
        assert running[0].run_id == run.run_id


class TestGetWaitingRun:
    def test_finds_waiting(self, registry: WorkflowRegistry):
        run = registry.create_run("test_workflow", chat_id=42, topic_id=7)
        run.status = WorkflowRunStatus.WAITING
        registry.update_run(run)

        found = registry.get_waiting_run(42, 7)
        assert found is not None
        assert found.run_id == run.run_id

    def test_no_match(self, registry: WorkflowRegistry):
        assert registry.get_waiting_run(999, None) is None


class TestPersistenceSurvivesReload:
    def test_reload(self, tmp_path: Path, tmp_workflows_dir: Path):
        runs_path = tmp_path / "runs.json"
        reg1 = WorkflowRegistry(tmp_workflows_dir, runs_path)
        run = reg1.create_run("test_workflow", chat_id=100)
        run.status = WorkflowRunStatus.RUNNING
        reg1.update_run(run)

        # Create a new registry instance reading the same files
        reg2 = WorkflowRegistry(tmp_workflows_dir, runs_path)
        fetched = reg2.get_run(run.run_id)
        assert fetched is not None
        assert fetched.status == WorkflowRunStatus.RUNNING
        assert fetched.chat_id == 100
