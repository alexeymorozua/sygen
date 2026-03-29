"""Telegram command handler for /skill: ClawHub marketplace integration."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from sygen_bot.orchestrator.registry import OrchestratorResult
from sygen_bot.orchestrator.selectors.models import Button, ButtonGrid
from sygen_bot.text.response_format import SEP, fmt

if TYPE_CHECKING:
    from sygen_bot.orchestrator.core import Orchestrator
    from sygen_bot.session.key import SessionKey

logger = logging.getLogger(__name__)

_HELP_TEXT = fmt(
    "**Skill Marketplace**",
    SEP,
    (
        "`/skill search <query>` — search ClawHub marketplace\n"
        "`/skill install <name>` — download, scan, and install a skill\n"
        "`/skill list` — list installed skills\n"
        "`/skill remove <name>` — remove an installed skill\n"
        "`/skill help` — this help"
    ),
)

# In-memory pending installs keyed by "chat_id:skill_name".
_pending_installs: dict[str, Path] = {}


async def cmd_skill(
    orch: Orchestrator, key: SessionKey, text: str,
) -> OrchestratorResult:
    """Handle /skill command and subcommands."""
    cfg = orch._config
    if not getattr(cfg, "skill_marketplace", None) or not cfg.skill_marketplace.enabled:
        return OrchestratorResult(
            text="Skill marketplace is not enabled. Set `skill_marketplace.enabled: true` in config.json.",
        )

    parts = text.strip().split(None, 2)
    sub = parts[1].strip().lower() if len(parts) > 1 else ""
    arg = parts[2].strip() if len(parts) > 2 else ""

    if sub == "help" or not sub:
        return OrchestratorResult(text=_HELP_TEXT)

    if sub == "search":
        return await _search(arg)

    if sub == "install":
        return await _install(orch, key, arg)

    if sub == "list":
        return _list(orch)

    if sub == "remove":
        return await _remove(orch, arg)

    return OrchestratorResult(text=_HELP_TEXT)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


_SEARCH_PAGE_SIZE = 5


async def _search(query: str, *, page: int = 0) -> OrchestratorResult:
    """Search ClawHub for skills with pagination."""
    if not query:
        return OrchestratorResult(text="Usage: `/skill search <query>`")

    from sygen_bot.skills.clawhub import search_skills

    # Fetch more results to enable paging.
    results = await search_skills(query, limit=50)
    if not results:
        return OrchestratorResult(text=f"No skills found for \"{query}\".")

    total = len(results)
    start = page * _SEARCH_PAGE_SIZE
    end = start + _SEARCH_PAGE_SIZE
    page_results = results[start:end]

    if not page_results and page > 0:
        page = 0
        start = 0
        end = _SEARCH_PAGE_SIZE
        page_results = results[start:end]

    lines: list[str] = []
    buttons: list[list[Button]] = []
    for sk in page_results:
        desc = sk.description[:80] if sk.description else "no description"
        author = f" by {sk.author}" if sk.author else ""
        lines.append(f"  **{sk.name}**{author}\n    {desc}")
        buttons.append([
            Button(text=f"Install {sk.name}", callback_data=f"skill_install:{sk.name}"),
        ])

    # Pagination buttons.
    nav: list[Button] = []
    if page > 0:
        nav.append(Button(
            text="\u2b05 Prev",
            callback_data=f"skill_page:{page - 1}:{query[:40]}",
        ))
    if end < total:
        nav.append(Button(
            text="Next \u27a1",
            callback_data=f"skill_page:{page + 1}:{query[:40]}",
        ))
    if nav:
        buttons.append(nav)

    page_label = f", page {page + 1}" if total > _SEARCH_PAGE_SIZE else ""
    header = f"**ClawHub Results** ({total}{page_label})"

    return OrchestratorResult(
        text=fmt(header, SEP, "\n".join(lines)),
        buttons=ButtonGrid(rows=buttons) if buttons else None,
    )


async def _install(
    orch: Orchestrator,
    key: SessionKey,
    name: str,
) -> OrchestratorResult:
    """Download a skill, scan it, show report, and ask for confirmation."""
    if not name:
        return OrchestratorResult(text="Usage: `/skill install <name>`")

    from sygen_bot.skills.clawhub import SkillNotFoundError, download_skill
    from sygen_bot.skills.scanner import ScanFinding, scan_skill

    # Download to temp directory.
    tmp = Path(tempfile.mkdtemp(prefix="clawhub_"))
    try:
        skill_path = await download_skill(name, tmp)
    except SkillNotFoundError:
        shutil.rmtree(tmp, ignore_errors=True)
        return OrchestratorResult(text=f"Skill \"{name}\" not found in ClawHub registry.")
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        logger.exception("Failed to download skill '%s'", name)
        return OrchestratorResult(text=f"Failed to download skill \"{name}\". Try again later.")

    # Run security scan.
    vt_key = _get_vt_key(orch)
    scan_result = await scan_skill(skill_path, vt_api_key=vt_key)

    # Count script files.
    scripts_dir = skill_path / "scripts"
    scan_dir = scripts_dir if scripts_dir.is_dir() else skill_path
    file_count = sum(1 for f in scan_dir.rglob("*") if f.is_file())

    # Build report.
    report = _format_scan_report(name, scan_result, file_count)

    # Store pending install for confirmation.
    pending_key = f"{key.chat_id}:{name}"
    _pending_installs[pending_key] = skill_path

    # Build buttons.
    if scan_result.is_safe:
        buttons = ButtonGrid(rows=[
            [
                Button(text="\u2705 Install", callback_data=f"skill_confirm:{name}"),
                Button(text="\u274c Cancel", callback_data=f"skill_cancel:{name}"),
            ],
        ])
    else:
        buttons = ButtonGrid(rows=[
            [
                Button(text="\u274c Cancel", callback_data=f"skill_cancel:{name}"),
                Button(text="\u26a0\ufe0f Install anyway", callback_data=f"skill_confirm:{name}"),
            ],
        ])

    return OrchestratorResult(text=report, buttons=buttons)


def _format_scan_report(
    name: str,
    scan_result: object,
    file_count: int,
) -> str:
    """Format scan results as a Telegram-friendly message."""
    from sygen_bot.skills.scanner import ScanResult

    assert isinstance(scan_result, ScanResult)

    lines: list[str] = [
        f"\U0001f50d Skill \"{name}\"",
        f"\U0001f4c1 Scripts: {file_count} file(s)",
    ]

    # Static scan summary.
    criticals = [f for f in scan_result.static_findings if f.severity == "critical"]
    warnings = [f for f in scan_result.static_findings if f.severity == "warning"]

    if not criticals and not warnings:
        lines.append("\U0001f6e1 Static scan: \u2705 Clean")
    else:
        parts: list[str] = []
        if criticals:
            parts.append(f"\u274c {len(criticals)} critical")
        if warnings:
            parts.append(f"\u26a0\ufe0f {len(warnings)} warning(s)")
        lines.append(f"\U0001f6e1 Static scan: {', '.join(parts)}")
        for finding in (criticals + warnings)[:5]:
            loc = f"line {finding.line}" if finding.line else ""
            lines.append(f"  - {finding.description} ({loc})")

    # VT summary.
    if scan_result.vt_results:
        total_detections = sum(vr.detections for vr in scan_result.vt_results.values())
        max_engines = max((vr.total_engines for vr in scan_result.vt_results.values()), default=0)
        if total_detections == 0:
            lines.append(f"\U0001f9a0 VirusTotal: \u2705 0/{max_engines} detections")
        else:
            lines.append(
                f"\U0001f9a0 VirusTotal: \u274c {total_detections}/{max_engines} detections"
            )
    else:
        lines.append("\U0001f9a0 VirusTotal: skipped (no API key)")

    return "\n".join(lines)


async def _remove(orch: Orchestrator, name: str) -> OrchestratorResult:
    """Remove an installed skill."""
    if not name:
        return OrchestratorResult(text="Usage: `/skill remove <name>`")

    from sygen_bot.skills.clawhub import remove_skill

    skills_dir = orch._paths.skills_dir
    if remove_skill(name, skills_dir):
        return OrchestratorResult(text=f"Removed skill \"{name}\".")
    return OrchestratorResult(text=f"Skill \"{name}\" is not installed.")


def _list(orch: Orchestrator) -> OrchestratorResult:
    """List installed skills."""
    from sygen_bot.skills.clawhub import list_installed_skills

    skills_dir = orch._paths.skills_dir
    installed = list_installed_skills(skills_dir)

    if not installed:
        return OrchestratorResult(text=fmt("**Installed Skills**", SEP, "No skills installed."))

    lines: list[str] = []
    for sk in installed:
        desc = f" — {sk.description}" if sk.description else ""
        lines.append(f"  **{sk.name}**{desc}")

    return OrchestratorResult(
        text=fmt(f"**Installed Skills** ({len(installed)})", SEP, "\n".join(lines)),
    )


async def handle_skill_callback(
    orch: Orchestrator,
    key: SessionKey,
    callback_data: str,
) -> OrchestratorResult | None:
    """Handle button callbacks from skill install flow.

    Returns None if the callback is not skill-related.
    """
    if not callback_data.startswith("skill_"):
        return None

    if callback_data.startswith("skill_confirm:"):
        name = callback_data[len("skill_confirm:"):]
        return await _confirm_install(orch, key, name)

    if callback_data.startswith("skill_cancel:"):
        name = callback_data[len("skill_cancel:"):]
        return _cancel_install(key, name)

    if callback_data.startswith("skill_install:"):
        name = callback_data[len("skill_install:"):]
        return await _install(orch, key, name)

    if callback_data.startswith("skill_page:"):
        # skill_page:<page>:<query>
        rest = callback_data[len("skill_page:"):]
        page_str, _, query = rest.partition(":")
        try:
            page = int(page_str)
        except ValueError:
            page = 0
        return await _search(query, page=page)

    return None


async def _confirm_install(
    orch: Orchestrator,
    key: SessionKey,
    name: str,
) -> OrchestratorResult:
    """Confirm and finalize skill installation."""
    from sygen_bot.skills.clawhub import install_skill

    pending_key = f"{key.chat_id}:{name}"
    skill_path = _pending_installs.pop(pending_key, None)

    if skill_path is None or not skill_path.exists():
        return OrchestratorResult(text=f"Install session for \"{name}\" expired. Try again.")

    skills_dir = orch._paths.skills_dir
    skills_dir.mkdir(parents=True, exist_ok=True)

    try:
        await install_skill(skill_path, skills_dir)
    finally:
        # Clean up temp directory.
        tmp_root = skill_path.parent
        shutil.rmtree(tmp_root, ignore_errors=True)

    return OrchestratorResult(text=f"\u2705 Skill \"{name}\" installed successfully.")


def _cancel_install(key: SessionKey, name: str) -> OrchestratorResult:
    """Cancel a pending install and clean up."""
    pending_key = f"{key.chat_id}:{name}"
    skill_path = _pending_installs.pop(pending_key, None)

    if skill_path is not None:
        tmp_root = skill_path.parent
        shutil.rmtree(tmp_root, ignore_errors=True)

    return OrchestratorResult(text=f"Installation of \"{name}\" cancelled.")


def _get_vt_key(orch: Orchestrator) -> str | None:
    """Get VirusTotal API key from config."""
    cfg = orch._config
    marketplace = getattr(cfg, "skill_marketplace", None)
    if marketplace and marketplace.virustotal_api_key:
        return marketplace.virustotal_api_key
    return None
