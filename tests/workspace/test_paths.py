"""Tests for SygenPaths and resolve_paths."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from sygen_bot.workspace.paths import SygenPaths, resolve_paths


def test_workspace_property() -> None:
    paths = SygenPaths(
        sygen_home=Path("/home/test/.sygen"),
        home_defaults=Path("/opt/sygen/workspace"),
        framework_root=Path("/opt/sygen"),
    )
    assert paths.workspace == Path("/home/test/.sygen/workspace")


def test_config_path() -> None:
    paths = SygenPaths(
        sygen_home=Path("/home/test/.sygen"),
        home_defaults=Path("/opt/sygen/workspace"),
        framework_root=Path("/opt/sygen"),
    )
    assert paths.config_path == Path("/home/test/.sygen/config/config.json")


def test_sessions_path() -> None:
    paths = SygenPaths(
        sygen_home=Path("/home/test/.sygen"),
        home_defaults=Path("/opt/sygen/workspace"),
        framework_root=Path("/opt/sygen"),
    )
    assert paths.sessions_path == Path("/home/test/.sygen/sessions.json")


def test_logs_dir() -> None:
    paths = SygenPaths(
        sygen_home=Path("/home/test/.sygen"),
        home_defaults=Path("/opt/sygen/workspace"),
        framework_root=Path("/opt/sygen"),
    )
    assert paths.logs_dir == Path("/home/test/.sygen/logs")


def test_home_defaults() -> None:
    paths = SygenPaths(
        sygen_home=Path("/x"),
        home_defaults=Path("/opt/sygen/workspace"),
        framework_root=Path("/opt/sygen"),
    )
    assert paths.home_defaults == Path("/opt/sygen/workspace")


def test_resolve_paths_explicit() -> None:
    paths = resolve_paths(sygen_home="/tmp/test_home", framework_root="/tmp/test_fw")
    assert paths.sygen_home == Path("/tmp/test_home").resolve()
    assert paths.framework_root == Path("/tmp/test_fw").resolve()


def test_resolve_paths_env_vars() -> None:
    with patch.dict(
        os.environ, {"SYGEN_HOME": "/tmp/env_home", "SYGEN_FRAMEWORK_ROOT": "/tmp/env_fw"}
    ):
        paths = resolve_paths()
        assert paths.sygen_home == Path("/tmp/env_home").resolve()
        assert paths.framework_root == Path("/tmp/env_fw").resolve()


def test_resolve_paths_defaults() -> None:
    with patch.dict(os.environ, {}, clear=True):
        env_clean = {
            k: v for k, v in os.environ.items() if k not in ("SYGEN_HOME", "SYGEN_FRAMEWORK_ROOT")
        }
        with patch.dict(os.environ, env_clean, clear=True):
            paths = resolve_paths()
            assert paths.sygen_home == (Path.home() / ".sygen").resolve()
