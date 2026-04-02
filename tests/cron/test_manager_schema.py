"""Test CronJob schema extensions."""

from __future__ import annotations

import json
from pathlib import Path

from sygen_bot.cron.manager import CronJob, CronManager


def test_cronjob_new_fields_defaults() -> None:
    """CronJob should accept new fields with None/empty defaults."""
    job = CronJob(
        id="test-1",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
    )

    # New fields should have None or empty defaults
    assert job.provider is None
    assert job.model is None
    assert job.reasoning_effort is None
    assert job.cli_parameters == []


def test_cronjob_new_fields_with_values() -> None:
    """CronJob should accept and store new field values."""
    job = CronJob(
        id="test-2",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
        provider="codex",
        model="gpt-5.2-codex",
        reasoning_effort="high",
        cli_parameters=["--fast", "--verbose"],
    )

    assert job.provider == "codex"
    assert job.model == "gpt-5.2-codex"
    assert job.reasoning_effort == "high"
    assert job.cli_parameters == ["--fast", "--verbose"]


def test_cronjob_to_dict_includes_new_fields() -> None:
    """CronJob.to_dict() should include new fields."""
    job = CronJob(
        id="test-3",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
        provider="codex",
        model="gpt-5.2-codex",
        reasoning_effort="high",
        cli_parameters=["--fast"],
    )

    data = job.to_dict()

    assert data["provider"] == "codex"
    assert data["model"] == "gpt-5.2-codex"
    assert data["reasoning_effort"] == "high"
    assert data["cli_parameters"] == ["--fast"]


def test_cronjob_to_dict_with_none_values() -> None:
    """CronJob.to_dict() should handle None values correctly."""
    job = CronJob(
        id="test-4",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
    )

    data = job.to_dict()

    # None values should be included as None (not omitted)
    assert "provider" in data
    assert data["provider"] is None
    assert "model" in data
    assert data["model"] is None
    assert "reasoning_effort" in data
    assert data["reasoning_effort"] is None
    assert "cli_parameters" in data
    assert data["cli_parameters"] == []


def test_cronjob_from_dict_with_new_fields() -> None:
    """CronJob.from_dict() should deserialize new fields."""
    data = {
        "id": "test-5",
        "title": "Test Job",
        "description": "Test description",
        "schedule": "0 * * * *",
        "task_folder": "test/",
        "agent_instruction": "Do something",
        "provider": "codex",
        "model": "gpt-5.2-codex",
        "reasoning_effort": "high",
        "cli_parameters": ["--fast", "--verbose"],
    }

    job = CronJob.from_dict(data)

    assert job.provider == "codex"
    assert job.model == "gpt-5.2-codex"
    assert job.reasoning_effort == "high"
    assert job.cli_parameters == ["--fast", "--verbose"]


def test_cronjob_from_dict_backward_compatibility() -> None:
    """CronJob.from_dict() should handle old JSON without new fields."""
    old_data = {
        "id": "test-6",
        "title": "Test Job",
        "description": "Test description",
        "schedule": "0 * * * *",
        "task_folder": "test/",
        "agent_instruction": "Do something",
        "enabled": True,
    }

    # Should not raise, should use defaults
    job = CronJob.from_dict(old_data)

    assert job.provider is None
    assert job.model is None
    assert job.reasoning_effort is None
    assert job.cli_parameters == []


def test_cronjob_round_trip_serialization() -> None:
    """CronJob should serialize and deserialize without data loss."""
    original = CronJob(
        id="test-7",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
        provider="codex",
        model="gpt-5.2-codex",
        reasoning_effort="high",
        cli_parameters=["--fast", "--verbose"],
    )

    # Serialize
    data = original.to_dict()

    # Deserialize
    restored = CronJob.from_dict(data)

    assert restored.id == original.id
    assert restored.provider == original.provider
    assert restored.model == original.model
    assert restored.reasoning_effort == original.reasoning_effort
    assert restored.cli_parameters == original.cli_parameters


def test_cron_manager_persists_new_fields(tmp_path: Path) -> None:
    """CronManager should persist new fields to disk."""
    jobs_path = tmp_path / "cron_jobs.json"

    manager = CronManager(jobs_path=jobs_path)

    job = CronJob(
        id="test-8",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
        provider="codex",
        model="gpt-5.2-codex",
        reasoning_effort="high",
        cli_parameters=["--fast"],
    )

    manager.add_job(job)

    # Read from disk
    loaded_data = json.loads(jobs_path.read_text())
    job_data = loaded_data["jobs"][0]

    assert job_data["provider"] == "codex"
    assert job_data["model"] == "gpt-5.2-codex"
    assert job_data["reasoning_effort"] == "high"
    assert job_data["cli_parameters"] == ["--fast"]


def test_cron_manager_loads_old_format(tmp_path: Path) -> None:
    """CronManager should load old JSON without new fields."""
    jobs_path = tmp_path / "cron_jobs.json"

    old_format = {
        "jobs": [
            {
                "id": "test-9",
                "title": "Old Job",
                "description": "Old description",
                "schedule": "0 * * * *",
                "task_folder": "test/",
                "agent_instruction": "Do something",
                "enabled": True,
                "created_at": "2025-01-01T00:00:00Z",
            },
        ],
    }

    jobs_path.write_text(json.dumps(old_format))

    manager = CronManager(jobs_path=jobs_path)
    jobs = manager.list_jobs()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "test-9"
    assert job.provider is None
    assert job.model is None
    assert job.reasoning_effort is None
    assert job.cli_parameters == []


def test_cron_manager_reload_preserves_new_fields(tmp_path: Path) -> None:
    """CronManager.reload() should preserve new fields."""
    jobs_path = tmp_path / "cron_jobs.json"

    manager = CronManager(jobs_path=jobs_path)

    job = CronJob(
        id="test-10",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
        provider="codex",
        model="gpt-5.2-codex",
        reasoning_effort="high",
        cli_parameters=["--fast"],
    )

    manager.add_job(job)

    # Reload from disk
    manager.reload()

    jobs = manager.list_jobs()
    assert len(jobs) == 1
    reloaded_job = jobs[0]

    assert reloaded_job.provider == "codex"
    assert reloaded_job.model == "gpt-5.2-codex"
    assert reloaded_job.reasoning_effort == "high"
    assert reloaded_job.cli_parameters == ["--fast"]


def test_empty_cli_parameters_persists_as_empty_list(tmp_path: Path) -> None:
    """Empty cli_parameters should persist as [], not None."""
    jobs_path = tmp_path / "cron_jobs.json"

    manager = CronManager(jobs_path=jobs_path)

    job = CronJob(
        id="test-11",
        title="Test Job",
        description="Test description",
        schedule="0 * * * *",
        task_folder="test/",
        agent_instruction="Do something",
        cli_parameters=[],
    )

    manager.add_job(job)

    # Read from disk and verify
    loaded_data = json.loads(jobs_path.read_text())
    job_data = loaded_data["jobs"][0]

    assert "cli_parameters" in job_data
    assert job_data["cli_parameters"] == []
    assert isinstance(job_data["cli_parameters"], list)

    # Reload and verify
    manager.reload()
    jobs = manager.list_jobs()
    reloaded_job = jobs[0]

    assert reloaded_job.cli_parameters == []
    assert isinstance(reloaded_job.cli_parameters, list)


# -- script_mode tests --


def test_script_mode_defaults() -> None:
    """script_mode defaults to False, script defaults to None."""
    job = CronJob(
        id="sm-1",
        title="T",
        description="D",
        schedule="* * * * *",
        task_folder="t",
        agent_instruction="x",
    )
    assert job.script_mode is False
    assert job.script is None


def test_script_mode_round_trip() -> None:
    """script_mode and script survive serialization."""
    job = CronJob(
        id="sm-2",
        title="Dashboard",
        description="D",
        schedule="0 19 * * *",
        task_folder="dashboard",
        agent_instruction="x",
        script_mode=True,
        script="scripts/dashboard.py",
    )
    data = job.to_dict()
    assert data["script_mode"] is True
    assert data["script"] == "scripts/dashboard.py"

    restored = CronJob.from_dict(data)
    assert restored.script_mode is True
    assert restored.script == "scripts/dashboard.py"


def test_script_mode_backward_compat() -> None:
    """Old jobs without script_mode fields load with defaults."""
    old = {
        "id": "old",
        "title": "Old",
        "schedule": "* * * * *",
        "task_folder": "old",
        "agent_instruction": "x",
    }
    job = CronJob.from_dict(old)
    assert job.script_mode is False
    assert job.script is None


def test_script_mode_persists(tmp_path: Path) -> None:
    """script_mode fields survive CronManager persist + reload."""
    jobs_path = tmp_path / "cron_jobs.json"
    manager = CronManager(jobs_path=jobs_path)
    manager.add_job(CronJob(
        id="sm-3",
        title="T",
        description="D",
        schedule="* * * * *",
        task_folder="t",
        agent_instruction="x",
        script_mode=True,
        script="scripts/test.py",
    ))
    manager.reload()
    job = manager.get_job("sm-3")
    assert job is not None
    assert job.script_mode is True
    assert job.script == "scripts/test.py"
