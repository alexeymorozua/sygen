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



def read_always_load_modules(paths: SygenPaths) -> str:
    """Read 'Always Load' memory modules (user.md, decisions.md).

    Scans the MAINMEMORY.md index for the 'Always Load' table and reads
    each referenced module file.  Returns concatenated content or empty string.
    """
    mainmemory = read_file(paths.mainmemory_path) or ""
    modules_dir = paths.memory_system_dir / "modules"
    if not modules_dir.is_dir():
        return ""

    # Parse Always Load table from MAINMEMORY.md
    in_always_load = False
    module_files: list[str] = []
    for line in mainmemory.splitlines():
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

    if not module_files:
        module_files = ["user.md", "decisions.md"]

    parts: list[str] = []
    for fname in module_files:
        content = read_file(modules_dir / fname)
        if content and content.strip():
            parts.append(f"# Memory: {fname}\n{content.strip()}")

    return "\n\n".join(parts)
