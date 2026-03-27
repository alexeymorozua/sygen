"""ClawHub marketplace integration — search, download, and install skills."""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_CLAWHUB_ORG = "openclaw"
_CLAWHUB_REPO = "skills"
_REQUEST_TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class SkillInfo:
    """Metadata for a ClawHub skill."""

    name: str
    author: str = ""
    description: str = ""
    url: str = ""
    version: str = ""
    files: list[str] = field(default_factory=list)


async def search_skills(query: str, *, limit: int = 10) -> list[SkillInfo]:
    """Search ClawHub GitHub registry for skills matching *query*.

    Uses GitHub code search scoped to the openclaw/skills repository.
    Falls back to repository content listing when the query is broad.
    """
    if not query.strip():
        return []

    results: list[SkillInfo] = []
    params: dict[str, str | int] = {
        "q": f"{query} repo:{_CLAWHUB_ORG}/{_CLAWHUB_REPO}",
        "per_page": limit,
    }

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{_GITHUB_API}/search/repositories",
                params={"q": f"{query} org:{_CLAWHUB_ORG} topic:skill", "per_page": limit},
            )
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                for item in data.get("items", []):
                    results.append(
                        SkillInfo(
                            name=item.get("name", ""),
                            author=item.get("owner", {}).get("login", ""),
                            description=item.get("description", "") or "",
                            url=item.get("html_url", ""),
                        )
                    )
                if results:
                    return results

            # Fallback: search code inside the monorepo.
            resp = await client.get(
                f"{_GITHUB_API}/search/code",
                params=params,
            )
            if resp.status_code == 200:
                data = resp.json()
                seen: set[str] = set()
                for item in data.get("items", []):
                    repo = item.get("repository", {})
                    path_parts = item.get("path", "").split("/")
                    skill_name = path_parts[0] if path_parts else repo.get("name", "")
                    if skill_name in seen:
                        continue
                    seen.add(skill_name)
                    results.append(
                        SkillInfo(
                            name=skill_name,
                            author=repo.get("owner", {}).get("login", ""),
                            description=repo.get("description", "") or "",
                            url=repo.get("html_url", ""),
                        )
                    )
        except httpx.HTTPError as exc:
            logger.warning("ClawHub search failed: %s", exc)

    return results


async def download_skill(name: str, temp_dir: Path) -> Path:
    """Download a skill from ClawHub registry into *temp_dir*.

    Tries two strategies:
    1. Standalone repo: ``openclaw/<name>``
    2. Monorepo subfolder: ``openclaw/skills/contents/<name>``

    Returns the local directory containing the downloaded skill files.
    """
    dest = temp_dir / name
    dest.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        # Strategy 1: standalone repo tarball.
        tarball_url = f"{_GITHUB_API}/repos/{_CLAWHUB_ORG}/{name}/tarball"
        try:
            resp = await client.get(tarball_url, follow_redirects=True)
            if resp.status_code == 200:
                await _extract_tarball(resp.content, dest)
                return dest
        except httpx.HTTPError:
            pass

        # Strategy 2: monorepo subfolder.
        contents_url = (
            f"{_GITHUB_API}/repos/{_CLAWHUB_ORG}/{_CLAWHUB_REPO}/contents/{name}"
        )
        try:
            resp = await client.get(contents_url)
            if resp.status_code == 200:
                body = resp.json()
                items: list[dict[str, Any]] = body if isinstance(body, list) else []
                for item in items:
                    if item.get("download_url"):
                        file_resp = await client.get(item["download_url"])
                        if file_resp.status_code == 200:
                            (dest / item["name"]).write_bytes(file_resp.content)
                return dest
        except httpx.HTTPError:
            pass

    msg = f"Skill '{name}' not found in ClawHub registry"
    raise SkillNotFoundError(msg)


class SkillNotFoundError(Exception):
    """Raised when a skill cannot be found in the registry."""


async def _extract_tarball(data: bytes, dest: Path) -> None:
    """Extract a gzip tarball into *dest*, flattening one top-level directory."""
    import asyncio
    import tarfile
    from io import BytesIO

    def _do_extract() -> None:
        with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tar:
            # GitHub tarballs have a single top-level dir like "user-repo-sha/"
            members = tar.getmembers()
            prefix = ""
            if members:
                prefix = members[0].name.split("/")[0] + "/"
            for member in members:
                if member.name == prefix.rstrip("/"):
                    continue
                member.name = member.name[len(prefix) :]
                if not member.name:
                    continue
                # Security: prevent path traversal.
                if member.name.startswith("..") or member.name.startswith("/"):
                    continue
                tar.extract(member, dest, filter="data")

    await asyncio.to_thread(_do_extract)


async def install_skill(skill_path: Path, skills_dir: Path) -> Path:
    """Copy a validated skill directory into the workspace skills folder.

    Returns the installed skill path.
    """
    name = skill_path.name
    target = skills_dir / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(skill_path, target)
    logger.info("Installed skill '%s' to %s", name, target)
    return target


def list_installed_skills(skills_dir: Path) -> list[SkillInfo]:
    """List locally installed skills from *skills_dir*."""
    if not skills_dir.is_dir():
        return []

    results: list[SkillInfo] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        # Try reading skill metadata from SKILL.md or package.json.
        desc = _read_skill_description(child)
        results.append(
            SkillInfo(
                name=child.name,
                description=desc,
            )
        )
    return results


def _read_skill_description(skill_dir: Path) -> str:
    """Try to extract a description from skill metadata files."""
    # Check SKILL.md first line.
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        first_line = skill_md.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
        return first_line.lstrip("# ").strip()

    # Check package.json.
    import json

    pkg = skill_dir / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            return str(data.get("description", ""))
        except (json.JSONDecodeError, OSError):
            pass

    return ""


def remove_skill(name: str, skills_dir: Path) -> bool:
    """Remove an installed skill. Returns True if removed."""
    target = skills_dir / name
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    logger.info("Removed skill '%s'", name)
    return True
