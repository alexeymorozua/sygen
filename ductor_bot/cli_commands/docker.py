"""Docker management CLI subcommands (``ductor docker ...``)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ductor_bot.workspace.paths import resolve_paths

_console = Console()

_DOCKER_SUBCOMMANDS = frozenset({"rebuild", "enable", "disable", "mount", "unmount", "mounts"})


def _parse_docker_subcommand(args: list[str]) -> str | None:
    """Extract the subcommand after 'docker' from CLI args."""
    found = False
    for a in args:
        if a.startswith("-"):
            continue
        if not found and a == "docker":
            found = True
            continue
        if found:
            return a if a in _DOCKER_SUBCOMMANDS else None
    return None


def _parse_docker_mount_arg(args: list[str]) -> str | None:
    """Extract the path argument after 'docker mount/unmount' from CLI args.

    Expects the form: ``ductor docker mount <path>`` where *args* is
    ``sys.argv[1:]`` (no ``ductor`` prefix).  Non-flag positionals are
    ``docker`` (1), ``mount``/``unmount`` (2), ``<path>`` (3).
    """
    positionals = [a for a in args if not a.startswith("-")]
    # positionals: ['docker', 'mount', '<path>']
    return positionals[2] if len(positionals) >= 3 else None


def print_docker_help() -> None:
    """Print the docker subcommand help table."""
    _console.print()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold green", min_width=36)
    table.add_column()
    table.add_row("ductor docker rebuild", "Remove container & image, rebuild on next start")
    table.add_row("ductor docker enable", "Enable Docker sandboxing")
    table.add_row("ductor docker disable", "Disable Docker sandboxing")
    table.add_row("ductor docker mount <path>", "Mount a host directory into the sandbox")
    table.add_row("ductor docker unmount <path>", "Remove a mounted directory")
    table.add_row("ductor docker mounts", "List all mounted directories")
    _console.print(
        Panel(table, title="[bold]Docker Commands[/bold]", border_style="blue", padding=(1, 0)),
    )
    _console.print()


def docker_read_config() -> tuple[Path, dict[str, object]] | None:
    """Read config.json and return (path, data) or None."""
    paths = resolve_paths()
    config_path = paths.config_path
    if not config_path.exists():
        _console.print("[bold red]Config not found. Run ductor first.[/bold red]")
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _console.print("[bold red]Failed to read config.[/bold red]")
        return None
    return config_path, data


def _stop_docker_container(container_name: str) -> None:
    """Stop and remove a Docker container."""
    if not shutil.which("docker"):
        return
    _console.print(f"[dim]Stopping Docker container '{container_name}'...[/dim]")
    subprocess.run(
        ["docker", "stop", "-t", "5", container_name],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        check=False,
    )
    _console.print("[green]Docker container stopped.[/green]")


def docker_set_enabled(*, enabled: bool) -> None:
    """Set docker.enabled in config.json and handle running state."""
    result = docker_read_config()
    if result is None:
        return
    config_path, data = result

    docker = data.setdefault("docker", {})
    if not isinstance(docker, dict):
        data["docker"] = docker = {}
    from ductor_bot.infra.json_store import atomic_json_save

    docker["enabled"] = enabled
    atomic_json_save(config_path, data)

    if not enabled:
        container = str(docker.get("container_name", "ductor-sandbox"))
        _stop_docker_container(container)

    state = "[green]enabled[/green]" if enabled else "[dim]disabled[/dim]"
    _console.print(f"Docker sandboxing: {state}")
    _console.print("[dim]Restart the bot to apply.[/dim]")


def docker_rebuild() -> None:
    """Stop bot, remove container and image, so they get rebuilt on restart."""
    from ductor_bot.cli_commands.lifecycle import stop_bot

    if not shutil.which("docker"):
        _console.print("[bold red]Docker not found.[/bold red]")
        return

    result = docker_read_config()
    container = "ductor-sandbox"
    image = "ductor-sandbox"
    if result is not None:
        _, data = result
        docker = data.get("docker", {})
        if isinstance(docker, dict):
            container = str(docker.get("container_name", container))
            image = str(docker.get("image_name", image))

    _console.print("[dim]Stopping bot...[/dim]")
    stop_bot()

    _console.print(f"[dim]Removing container '{container}'...[/dim]")
    subprocess.run(["docker", "rm", "-f", container], capture_output=True, check=False)

    _console.print(f"[dim]Removing image '{image}'...[/dim]")
    subprocess.run(["docker", "rmi", image], capture_output=True, check=False)

    _console.print(
        "[green]Done.[/green] Image will be rebuilt on next bot start.\n"
        "[dim]If running as a service, it will restart automatically.[/dim]"
    )


def _expand_path(raw: str) -> Path:
    """Expand env vars and ``~`` in a path string."""
    return Path(os.path.expandvars(raw)).expanduser()


def _docker_get_mounts(data: dict[str, object]) -> list[object]:
    """Return the ``docker.mounts`` list from config, ensuring it exists."""
    docker = data.setdefault("docker", {})
    if not isinstance(docker, dict):
        data["docker"] = docker = {}
    raw = docker.get("mounts")
    if not isinstance(raw, list):
        raw = []
        docker["mounts"] = raw
    return raw


def _is_duplicate_mount(mounts: list[object], resolved_str: str) -> bool:
    """Return True if *resolved_str* already exists in the mount list."""
    for existing in mounts:
        if not isinstance(existing, str):
            continue
        try:
            if str(_expand_path(existing).resolve()) == resolved_str:
                return True
        except OSError:
            continue
    return False


def docker_mount(args: list[str]) -> None:
    """Add a host directory to the Docker sandbox mounts."""
    raw_path = _parse_docker_mount_arg(args)
    if not raw_path:
        _console.print("[bold red]Usage: ductor docker mount <path>[/bold red]")
        return

    expanded = _expand_path(raw_path)
    try:
        resolved = expanded.resolve(strict=True)
    except OSError:
        _console.print(f"[bold red]Path does not exist: {raw_path}[/bold red]")
        return
    if not resolved.is_dir():
        _console.print(f"[bold red]Not a directory: {raw_path}[/bold red]")
        return

    result = docker_read_config()
    if result is None:
        return
    config_path, data = result
    mounts = _docker_get_mounts(data)
    resolved_str = str(resolved)

    if _is_duplicate_mount(mounts, resolved_str):
        _console.print(f"[dim]Already mounted: {resolved}[/dim]")
        return

    from ductor_bot.infra.json_store import atomic_json_save

    mounts.append(resolved_str)
    atomic_json_save(config_path, data)

    from ductor_bot.infra.docker import resolve_mount_target

    pair = resolve_mount_target(resolved_str, set())
    target_info = f" -> [cyan]{pair[1]}[/cyan]" if pair else ""
    _console.print(f"[green]Mounted:[/green] {resolved}{target_info}")
    _console.print("[dim]Restart the bot (or rebuild the container) to apply.[/dim]")


def _find_mount_entry(mounts: list[object], raw_path: str) -> str | None:
    """Find a matching entry in the mounts list by exact, resolved, or basename match."""
    expanded = _expand_path(raw_path)
    try:
        resolved_str = str(expanded.resolve())
    except OSError:
        resolved_str = str(expanded)
    query_basename = expanded.name

    for entry in mounts:
        if not isinstance(entry, str):
            continue
        if entry in (raw_path, resolved_str):
            return entry
        try:
            if str(_expand_path(entry).resolve()) == resolved_str:
                return entry
        except OSError:
            pass
        if Path(entry).name == query_basename:
            return entry
    return None


def docker_unmount(args: list[str]) -> None:
    """Remove a host directory from the Docker sandbox mounts."""
    raw_path = _parse_docker_mount_arg(args)
    if not raw_path:
        _console.print("[bold red]Usage: ductor docker unmount <path>[/bold red]")
        return

    result = docker_read_config()
    if result is None:
        return
    config_path, data = result

    docker = data.get("docker", {})
    if not isinstance(docker, dict) or not isinstance(docker.get("mounts"), list):
        _console.print("[dim]No mounts configured.[/dim]")
        return
    mounts: list[object] = docker["mounts"]

    to_remove = _find_mount_entry(mounts, raw_path)
    if to_remove is None:
        _console.print(f"[bold red]Mount not found: {raw_path}[/bold red]")
        return

    from ductor_bot.infra.json_store import atomic_json_save

    mounts.remove(to_remove)
    atomic_json_save(config_path, data)
    _console.print(f"[green]Unmounted:[/green] {to_remove}")
    _console.print("[dim]Restart the bot (or rebuild the container) to apply.[/dim]")


def docker_list_mounts() -> None:
    """List all configured Docker sandbox mounts."""
    result = docker_read_config()
    if result is None:
        return
    _, data = result

    docker = data.get("docker", {})
    mounts = docker.get("mounts", []) if isinstance(docker, dict) else []
    if not isinstance(mounts, list) or not mounts:
        _console.print("[dim]No mounts configured.[/dim]")
        _console.print("[dim]Use 'ductor docker mount <path>' to add one.[/dim]")
        return

    from ductor_bot.infra.docker import resolve_mount_target

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Host Path", style="bold")
    table.add_column("Container Path", style="cyan")
    table.add_column("Status")

    used_names: set[str] = set()
    for entry in mounts:
        if not isinstance(entry, str):
            continue
        pair = resolve_mount_target(entry, used_names)
        if pair is not None:
            host_resolved, container_target = pair
            table.add_row(str(host_resolved), container_target, "[green]OK[/green]")
        else:
            table.add_row(entry, "-", "[red]not found[/red]")

    _console.print(table)


def docker_container_name() -> str:
    """Return the configured Docker container name or default."""
    result = docker_read_config()
    if result is None:
        return "ductor-sandbox"
    _, data = result
    docker = data.get("docker", {})
    if isinstance(docker, dict):
        return str(docker.get("container_name", "ductor-sandbox"))
    return "ductor-sandbox"


def cmd_docker(args: list[str]) -> None:
    """Handle 'ductor docker <subcommand>'."""
    sub = _parse_docker_subcommand(args)
    if sub is None:
        print_docker_help()
        return

    dispatch: dict[str, Callable[[], None]] = {
        "rebuild": docker_rebuild,
        "enable": lambda: docker_set_enabled(enabled=True),
        "disable": lambda: docker_set_enabled(enabled=False),
        "mount": lambda: docker_mount(args),
        "unmount": lambda: docker_unmount(args),
        "mounts": docker_list_mounts,
    }
    _console.print()
    dispatch[sub]()
    _console.print()
