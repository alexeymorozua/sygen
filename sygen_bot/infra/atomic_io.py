"""Atomic file write primitives.

All persistent writes in the codebase should funnel through these helpers.
They use ``tempfile.mkstemp`` + ``os.replace`` for POSIX-atomic semantics:
a partial write can never leave a corrupt target file.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def atomic_text_save(
    path: Path, content: str, *, encoding: str = "utf-8", mode: int | None = None
) -> None:
    """Write *content* to *path* atomically via temp file + rename.

    Creates parent directories if they don't exist.
    If *mode* is given (e.g. ``0o600``), apply it after the rename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            fd = -1  # fdopen owns the fd now
            f.write(content)
        tmp.replace(path)
        if mode is not None:
            path.chmod(mode)
    except BaseException:
        if fd >= 0:
            with contextlib.suppress(OSError):
                os.close(fd)
        tmp.unlink(missing_ok=True)
        raise


def atomic_bytes_save(path: Path, data: bytes, *, mode: int | None = None) -> None:
    """Write *data* to *path* atomically via temp file + rename.

    Creates parent directories if they don't exist.
    If *mode* is given (e.g. ``0o600``), apply it after the rename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    tmp = Path(tmp_str)
    try:
        os.write(fd, data)
        os.close(fd)
        fd = -1  # already closed
        tmp.replace(path)
        if mode is not None:
            path.chmod(mode)
    except BaseException:
        if fd >= 0:
            with contextlib.suppress(OSError):
                os.close(fd)
        tmp.unlink(missing_ok=True)
        raise
