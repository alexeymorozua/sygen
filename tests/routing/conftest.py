"""Shared fixtures for routing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sygen_bot.config import AgentConfig
from sygen_bot.workspace.init import init_workspace
from sygen_bot.workspace.paths import DuctorPaths
from tests.orchestrator.conftest import setup_framework


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[DuctorPaths, AgentConfig]:
    """Fully initialized workspace with models and config."""
    fw_root = tmp_path / "fw"
    setup_framework(fw_root)
    paths = DuctorPaths(
        ductor_home=tmp_path / "home", home_defaults=fw_root / "workspace", framework_root=fw_root
    )
    init_workspace(paths)
    config = AgentConfig()
    return paths, config
