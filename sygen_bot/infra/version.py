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


# ---------------------------------------------------------------------------
# CLI auto-update: detect install type + perform update without sudo
# ---------------------------------------------------------------------------


class CLIInstallType:
    """Installation type of a CLI tool."""

    STANDALONE = "standalone"  # e.g. claude in ~/.local/bin (self-updating)
    NPM_USER = "npm_user"  # npm --prefix ~/.local or ~/.npm-global
    NPM_GLOBAL = "npm_global"  # npm -g (requires sudo)
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CLIUpdateResult:
    """Result of an auto-update attempt for one CLI tool."""

    name: str
    old_version: str
    new_version: str
    success: bool
    method: str  # "standalone", "npm_user", "skipped_needs_sudo", "error"
    message: str = ""


def _detect_cli_install_type(binary: str) -> str:
    """Detect how a CLI tool was installed.

    Returns one of CLIInstallType constants.

    Detection logic:
    - If binary path is under ~/.local/ → standalone or npm_user
      - If binary has a built-in ``update`` subcommand → standalone
      - Otherwise → npm_user
    - If binary path is under a system dir (/usr/local/, /usr/) → npm_global
    - If binary path is under /opt/homebrew/ → npm_user (no sudo on macOS)
    """
    path = shutil.which(binary)
    if not path:
        return CLIInstallType.UNKNOWN

    from pathlib import Path

    resolved = Path(path).resolve()
    home = Path.home()

    # User-local installs (no sudo needed)
    if str(resolved).startswith(str(home)):
        # Check if it's a standalone binary with self-update capability
        # Claude standalone lives in ~/.local/ and supports `claude update`
        if binary == "claude":
            return CLIInstallType.STANDALONE
        return CLIInstallType.NPM_USER

    # Homebrew on macOS — typically owned by user, no sudo
    if str(resolved).startswith("/opt/homebrew/"):
        return CLIInstallType.NPM_USER

    # System-wide installs require sudo
    if str(resolved).startswith(("/usr/local/", "/usr/")):
        return CLIInstallType.NPM_GLOBAL

    return CLIInstallType.UNKNOWN


async def _auto_update_standalone(binary: str) -> tuple[bool, str]:
    """Update a standalone CLI (e.g. ``claude update``)."""
    output = await _run_cmd(binary, "update", timeout=120.0)
    if output is None:
        return False, f"{binary} update command failed or timed out"
    return True, output


async def _auto_update_npm_user(
    binary: str,
    npm_pkg: str,
) -> tuple[bool, str]:
    """Update an npm package in user-space (no sudo).

    Tries several strategies:
    1. ``npm update <pkg> --prefix ~/.local``
    2. ``npm install <pkg>@latest --prefix ~/.local``
    """
    home = str(Path.home())
    prefix = f"{home}/.local"

    # Try update first
    proc = await asyncio.create_subprocess_exec(
        "npm", "update", npm_pkg, "--prefix", prefix,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120.0)
    except asyncio.TimeoutError:
        proc.kill()
        return False, "npm update timed out"

    output = stdout.decode(errors="replace") if stdout else ""
    if (proc.returncode or 0) == 0:
        return True, output

    # Fallback: fresh install
    proc2 = await asyncio.create_subprocess_exec(
        "npm", "install", f"{npm_pkg}@latest", "--prefix", prefix,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=120.0)
    except asyncio.TimeoutError:
        proc2.kill()
        return False, "npm install timed out"

    output2 = stdout2.decode(errors="replace") if stdout2 else ""
    return (proc2.returncode or 0) == 0, output2


async def auto_update_cli(
    binary: str,
    npm_pkg: str | None,
    current_version: str,
    latest_version: str,
) -> CLIUpdateResult:
    """Attempt to auto-update a CLI tool without sudo.

    Returns a CLIUpdateResult describing what happened.
    """
    install_type = _detect_cli_install_type(binary)

    if install_type == CLIInstallType.STANDALONE:
        ok, msg = await _auto_update_standalone(binary)
        if ok:
            new_ver = await _get_cli_version(binary) or latest_version
            return CLIUpdateResult(
                name=f"{binary} CLI",
                old_version=current_version,
                new_version=new_ver,
                success=True,
                method="standalone",
                message=msg,
            )
        return CLIUpdateResult(
            name=f"{binary} CLI",
            old_version=current_version,
            new_version=current_version,
            success=False,
            method="standalone",
            message=msg,
        )

    if install_type == CLIInstallType.NPM_USER and npm_pkg:
        ok, msg = await _auto_update_npm_user(binary, npm_pkg)
        if ok:
            new_ver = await _get_cli_version(binary) or latest_version
            return CLIUpdateResult(
                name=f"{binary} CLI",
                old_version=current_version,
                new_version=new_ver,
                success=True,
                method="npm_user",
                message=msg,
            )
        return CLIUpdateResult(
            name=f"{binary} CLI",
            old_version=current_version,
            new_version=current_version,
            success=False,
            method="npm_user",
            message=msg,
        )

    if install_type == CLIInstallType.NPM_GLOBAL:
        return CLIUpdateResult(
            name=f"{binary} CLI",
            old_version=current_version,
            new_version=current_version,
            success=False,
            method="skipped_needs_sudo",
            message=(
                f"{binary} CLI is installed globally and requires sudo to update. "
                "Reinstall in user-space to enable auto-updates."
            ),
        )

    return CLIUpdateResult(
        name=f"{binary} CLI",
        old_version=current_version,
        new_version=current_version,
        success=False,
        method="unknown",
        message=f"Could not determine install type for {binary}.",
    )


async def auto_update_all_cli() -> list[CLIUpdateResult]:
    """Check and auto-update all CLI tools that have updates available.

    Returns results only for CLIs that had updates available.
    """
    results: list[CLIUpdateResult] = []

    for binary, npm_pkg, _pip_pkg in _CLI_TOOLS:
        current = await _get_cli_version(binary)
        if not current:
            continue

        latest: str | None = None
        if npm_pkg:
            latest = await _get_npm_latest(npm_pkg)

        if not latest:
            continue

        if _parse_version(latest) <= _parse_version(current):
            continue

        logger.info(
            "Auto-updating %s CLI: %s -> %s", binary, current, latest,
        )
        result = await auto_update_cli(binary, npm_pkg, current, latest)
        results.append(result)

    return results
