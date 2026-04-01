"""Package version checking against PyPI, npm, and GitHub Releases."""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import shutil
import time
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

_PYPI_URL = "https://pypi.org/pypi/sygen/json"
_PYPI_PKG_URL = "https://pypi.org/pypi/{package}/json"
_GITHUB_RELEASES_URL = "https://api.github.com/repos/alexeymorozua/sygen/releases"
_PACKAGE_NAME = "sygen"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


def get_current_version() -> str:
    """Return the installed version of sygen."""
    try:
        return importlib.metadata.version(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse dotted version string into a comparable tuple."""
    parts: list[int] = []
    for segment in v.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            break
    return tuple(parts)


@dataclass(frozen=True, slots=True)
class VersionInfo:
    """Result of a PyPI version check."""

    current: str
    latest: str
    update_available: bool
    summary: str


async def check_pypi(*, fresh: bool = False) -> VersionInfo | None:
    """Check PyPI for the latest version. Returns None on failure.

    When ``fresh=True``, request with no-cache headers and a cache-busting
    query parameter to reduce stale CDN/cache responses.
    """
    current = get_current_version()
    headers = None
    params = None
    if fresh:
        headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
        params = {"_": str(time.time_ns())}

    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.get(_PYPI_URL, headers=headers, params=params) as resp,
        ):
            if resp.status != 200:
                return None
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        logger.debug("PyPI version check failed", exc_info=True)
        return None

    info = data.get("info", {})
    latest = info.get("version", "")
    if not latest:
        return None

    summary = info.get("summary", "")
    update_available = _parse_version(latest) > _parse_version(current)
    return VersionInfo(
        current=current,
        latest=latest,
        update_available=update_available,
        summary=summary,
    )


async def fetch_changelog(version: str) -> str | None:
    """Fetch release notes for *version* from GitHub Releases.

    Tries ``v{version}`` tag first, then ``{version}`` without prefix.
    Returns the release body (Markdown) or ``None`` on failure.
    """
    headers = {"Accept": "application/vnd.github+json"}
    for tag in (f"v{version}", version):
        url = f"{_GITHUB_RELEASES_URL}/tags/{tag}"
        try:
            async with (
                aiohttp.ClientSession(timeout=_TIMEOUT, headers=headers) as session,
                session.get(url) as resp,
            ):
                if resp.status != 200:
                    continue
                data = await resp.json()
                body: str = data.get("body", "")
                if body:
                    return body.strip()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            logger.debug("GitHub release fetch failed for tag %s", tag, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# System-wide update checks (CLI tools + pip optional deps)
# ---------------------------------------------------------------------------

# CLI tools: (binary_name, npm_package | None, pip_package | None)
_CLI_TOOLS: list[tuple[str, str | None, str | None]] = [
    ("claude", "@anthropic-ai/claude-code", None),
    ("gemini", "@google/gemini-cli", None),
    ("codex", "@openai/codex", None),
]

# pip optional deps to monitor (package_name, import_name)
_PIP_OPTIONAL_DEPS: list[tuple[str, str]] = [
    ("chromadb", "chromadb"),
    ("sentence-transformers", "sentence_transformers"),
]


@dataclass(frozen=True, slots=True)
class ComponentUpdate:
    """A single updatable component."""

    name: str
    current: str
    latest: str


@dataclass(frozen=True, slots=True)
class SystemUpdatesInfo:
    """Collection of available system updates."""

    updates: list[ComponentUpdate] = field(default_factory=list)

    @property
    def has_updates(self) -> bool:
        return len(self.updates) > 0


async def _run_cmd(*args: str, timeout: float = 10.0) -> str | None:
    """Run a command and return stripped stdout, or None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0 and stdout:
            return stdout.decode(errors="replace").strip()
    except (OSError, asyncio.TimeoutError):
        pass
    return None


async def _get_cli_version(binary: str) -> str | None:
    """Get installed CLI version via ``<binary> --version``."""
    if not shutil.which(binary):
        return None
    raw = await _run_cmd(binary, "--version")
    if not raw:
        return None
    # Parse version from output like "2.1.89 (Claude Code)" or "0.35.3"
    first_line = raw.splitlines()[0]
    # Take first token that looks like a version
    for token in first_line.split():
        if token[0].isdigit():
            return token.rstrip(",;)")
    return first_line


async def _get_npm_latest(package: str) -> str | None:
    """Get latest npm package version."""
    if not shutil.which("npm"):
        return None
    raw = await _run_cmd("npm", "show", package, "version", timeout=15.0)
    return raw if raw and raw[0].isdigit() else None


async def _get_pypi_latest(package: str) -> str | None:
    """Get latest PyPI package version via JSON API."""
    url = _PYPI_PKG_URL.format(package=package)
    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.get(url) as resp,
        ):
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("info", {}).get("version") or None
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return None


async def _get_pip_installed(package: str) -> str | None:
    """Get installed pip package version."""
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


async def _check_cli_tool(
    binary: str,
    npm_pkg: str | None,
    pip_pkg: str | None,
) -> ComponentUpdate | None:
    """Check a single CLI tool for updates."""
    current = await _get_cli_version(binary)
    if not current:
        return None  # not installed

    latest: str | None = None
    if npm_pkg:
        latest = await _get_npm_latest(npm_pkg)
    if not latest and pip_pkg:
        latest = await _get_pypi_latest(pip_pkg)

    if not latest:
        return None

    if _parse_version(latest) > _parse_version(current):
        return ComponentUpdate(name=f"{binary} CLI", current=current, latest=latest)
    return None


async def _check_pip_dep(package: str, import_name: str) -> ComponentUpdate | None:
    """Check a single pip optional dependency for updates."""
    current = await _get_pip_installed(package)
    if not current:
        return None  # not installed

    latest = await _get_pypi_latest(package)
    if not latest:
        return None

    if _parse_version(latest) > _parse_version(current):
        return ComponentUpdate(name=package, current=current, latest=latest)
    return None


async def check_system_updates() -> SystemUpdatesInfo:
    """Check all CLI tools and pip optional deps for updates.

    Runs all checks concurrently for speed.
    """
    tasks: list[asyncio.Task[ComponentUpdate | None]] = []

    for binary, npm_pkg, pip_pkg in _CLI_TOOLS:
        tasks.append(asyncio.create_task(_check_cli_tool(binary, npm_pkg, pip_pkg)))

    for package, import_name in _PIP_OPTIONAL_DEPS:
        tasks.append(asyncio.create_task(_check_pip_dep(package, import_name)))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    updates = [r for r in results if isinstance(r, ComponentUpdate)]

    return SystemUpdatesInfo(updates=updates)
