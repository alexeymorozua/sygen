"""Workspace file reader: safe reads with fallback defaults."""

from __future__ import annotations

import logging
from pathlib import Path

from sygen_bot.workspace.paths import SygenPaths

logger = logging.getLogger(__name__)


def read_file(path: Path) -> str | None:
    """Read a file, returning None if it does not exist or cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning("Failed to read file: %s", path, exc_info=True)
        return None


def read_mainmemory(paths: SygenPaths) -> str:
    """Read MAINMEMORY.md, returning empty string if missing."""
    return read_file(paths.mainmemory_path) or ""


def read_cron_results(paths: SygenPaths) -> str:
    """Read all per-job cron result buffers, returning empty string if none."""
    results_dir = paths.cron_results_dir
    if not results_dir.is_dir():
        return ""
    parts: list[str] = []
    for md_file in sorted(results_dir.glob("*.md")):
        content = read_file(md_file)
        if content and content.strip():
            parts.append(content.strip())
    if not parts:
        return ""
    return "# Latest Cron Results\n\n" + "\n\n---\n\n".join(parts)


def clear_cron_results(paths: SygenPaths) -> None:
    """Remove all cron result buffer files."""
    results_dir = paths.cron_results_dir
    if not results_dir.is_dir():
        return
    try:
        for md_file in results_dir.glob("*.md"):
            md_file.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to clear cron results buffer", exc_info=True)



_DEFAULT_ALWAYS_LOAD = ["user.md", "decisions.md"]


def _parse_always_load_filenames(mainmemory_text: str) -> list[str]:
    """Extract Always Load module filenames from MAINMEMORY.md text.

    Returns deduplicated list preserving order, or defaults if none found.
    """
    in_always_load = False
    module_files: list[str] = []
    for line in mainmemory_text.splitlines():
        if "Always Load" in line:
            in_always_load = True
            continue
        if in_always_load and line.startswith("###"):
            break  # next section
        if in_always_load and line.startswith("|") and "modules/" in line:
            for part in line.split("modules/"):
                if part and part[0] != "|":
                    fname = part.split(")")[0].split("|")[0].split("]")[0].strip()
                    if fname.endswith(".md"):
                        module_files.append(fname)

    # Deduplicate: markdown links like [modules/x.md](modules/x.md)
    # produce each filename twice after split("modules/").
    module_files = list(dict.fromkeys(module_files))
    return module_files or list(_DEFAULT_ALWAYS_LOAD)


def _read_modules(
    modules_dir: Path,
    filenames: list[str],
    *,
    max_lines_per_module: int = 0,
) -> str:
    """Read and concatenate module files.

    Args:
        max_lines_per_module: If >0, truncate each module to this many lines.
    """
    parts: list[str] = []
    for fname in filenames:
        content = read_file(modules_dir / fname)
        if not content or not content.strip():
            continue
        text = content.strip()
        if max_lines_per_module > 0:
            lines = text.splitlines()
            if len(lines) > max_lines_per_module:
                text = "\n".join(lines[:max_lines_per_module]) + "\n[...]"
        parts.append(f"# Memory: {fname}\n{text}")
    return "\n\n".join(parts)


def read_always_load_modules(paths: SygenPaths) -> str:
    """Read 'Always Load' memory modules (full content, for session start)."""
    mainmemory = read_file(paths.mainmemory_path) or ""
    modules_dir = paths.memory_system_dir / "modules"
    if not modules_dir.is_dir():
        return ""
    filenames = _parse_always_load_filenames(mainmemory)
    return _read_modules(modules_dir, filenames)


def read_always_load_modules_compact(
    modules_dir: Path,
    mainmemory_path: Path,
    *,
    max_lines_per_module: int = 30,
) -> str:
    """Read 'Always Load' modules with per-module line limit (for hooks)."""
    if not modules_dir.is_dir():
        return ""
    mainmemory = read_file(mainmemory_path) or ""
    filenames = _parse_always_load_filenames(mainmemory)
    return _read_modules(
        modules_dir, filenames, max_lines_per_module=max_lines_per_module,
    )
