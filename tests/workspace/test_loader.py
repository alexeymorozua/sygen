"""Tests for workspace file reader."""

from __future__ import annotations

from pathlib import Path

from sygen_bot.workspace.loader import read_always_load_modules, read_file, read_mainmemory
from sygen_bot.workspace.paths import SygenPaths


def _make_paths(tmp_path: Path) -> SygenPaths:
    fw = tmp_path / "fw"
    return SygenPaths(
        sygen_home=tmp_path / "home", home_defaults=fw / "workspace", framework_root=fw
    )


# -- read_file --


def test_read_existing_file(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("Hello world")
    assert read_file(f) == "Hello world"


def test_read_nonexistent_file(tmp_path: Path) -> None:
    assert read_file(tmp_path / "missing.md") is None


def test_read_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.md"
    f.write_text("")
    assert read_file(f) == ""


# -- read_mainmemory --


def test_read_mainmemory_exists(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    paths.memory_system_dir.mkdir(parents=True)
    paths.mainmemory_path.write_text("# Memories\n- Learned X")
    result = read_mainmemory(paths)
    assert result == "# Memories\n- Learned X"


def test_read_mainmemory_missing(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    assert read_mainmemory(paths) == ""


# -- read_always_load_modules --


def test_always_load_modules_no_duplicates(tmp_path: Path) -> None:
    """Markdown link format should not cause duplicate module loading."""
    paths = _make_paths(tmp_path)
    modules_dir = paths.memory_system_dir / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "user.md").write_text("User info here")
    (modules_dir / "decisions.md").write_text("Decision info here")

    # Simulate real MAINMEMORY.md with markdown links (each contains modules/ twice)
    paths.mainmemory_path.write_text(
        "### Always Load\n"
        "| Module | Description | Path |\n"
        "|--------|-------------|------|\n"
        "| user | User profile | [modules/user.md](modules/user.md) |\n"
        "| decisions | Decisions | [modules/decisions.md](modules/decisions.md) |\n"
        "### Load On Demand\n"
    )

    result = read_always_load_modules(paths)
    # Each module content should appear exactly once
    assert result.count("User info here") == 1
    assert result.count("Decision info here") == 1
