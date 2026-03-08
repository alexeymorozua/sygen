"""Centralised loading of user-defined environment secrets from ``~/.ductor/.env``.

The file uses standard dotenv syntax::

    # Comment
    PPLX_API_KEY=sk-xxx
    DEEPSEEK_API_KEY=sk-yyy
    export MY_VAR="quoted value"

Loaded once per process and cached.  Values are injected into CLI
subprocesses (host and Docker) but never override variables that are
already set in the environment.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_cache: dict[str, str] | None = None
_cache_path: Path | None = None


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Parse a ``.env`` file into a ``{key: value}`` dict.

    Supports ``#`` comments, ``export`` prefix, single/double quotes.
    """
    result: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return result

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, sep, value = line.partition("=")
        if sep != "=":
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        # Strip matching quotes.
        if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
            value = value[1:-1]
        else:
            # Remove inline comment (unquoted values only).
            value = value.split("#", 1)[0].strip()
        result[key] = value

    return result


def load_env_secrets(env_file: Path) -> dict[str, str]:
    """Load and cache secrets from *env_file*.

    Subsequent calls with the same path return the cached result.
    Call :func:`clear_cache` to force a re-read (e.g. in tests).
    """
    global _cache, _cache_path  # noqa: PLW0603
    if _cache is not None and _cache_path == env_file:
        return _cache

    if env_file.is_file():
        _cache = _parse_dotenv(env_file)
        _cache_path = env_file
        if _cache:
            logger.info("Loaded %d secret(s) from %s", len(_cache), env_file)
        return _cache

    _cache = {}
    _cache_path = env_file
    return _cache


def clear_cache() -> None:
    """Reset the cached secrets (for tests)."""
    global _cache, _cache_path  # noqa: PLW0603
    _cache = None
    _cache_path = None
