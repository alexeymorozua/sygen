# Skill Marketplace (ClawHub)

Browse, search, and install community skills from [OpenClaw's ClawHub](https://github.com/openclaw/skills) registry — with two-layer security scanning before installation.

## Files

- `sygen_bot/skills/clawhub.py`: `search_skills()`, `download_skill()`, `install_skill()`, `list_installed()`, `remove_skill()` — GitHub API wrapper for ClawHub registry
- `sygen_bot/skills/scanner.py`: `SecurityScanner` — static analysis + VirusTotal hash checking
- `sygen_bot/skills/commands.py`: `/skill` Telegram command handler with subcommands

## Architecture

```text
User → /skill search <query>
    → ClawHub GitHub API → results list

User → /skill install <name>
    → download to temp dir
    → SecurityScanner
        ├─ static analysis (7 critical + 13 warning patterns)
        └─ VirusTotal API v3 (SHA-256 hash check)
    → show scan report
    → user confirms → install to workspace/skills/
```

## Security scanning

Every skill is scanned before installation. The scanner runs two checks:

**Static analysis** — regex patterns against all skill files:
- Critical (blocks install with warning): `eval()`, `exec()`, `compile()`, `__import__()`, `importlib`, `marshal.loads`, `pickle.loads`
- Warning (shown but does not block): `subprocess`, `requests`, `httpx`, network calls, sensitive path access (`~/.ssh`, `~/.aws`, `.env`), base64/codecs decode, `os.system`, `ctypes`

**VirusTotal** — SHA-256 hash lookup via API v3:
- Checks each file against known malware signatures
- Requires a free API key (optional, static analysis works without it)
- Results show detection ratio (e.g., "2/72 engines flagged")

The scan report is shown to the user before installation. The user decides whether to proceed — sygen does not auto-block based on warnings.

## Configuration

```json
{
  "skill_marketplace": {
    "enabled": true,
    "virustotal_api_key": ""
  }
}
```

VirusTotal API key is optional. Without it, only static analysis runs. Get a free key at [virustotal.com](https://www.virustotal.com/).

## Telegram commands

- `/skill search <query>` — search ClawHub for skills
- `/skill install <name>` — download, scan, and install a skill
- `/skill list` — list installed marketplace skills
- `/skill remove <name>` — remove an installed skill
- `/skill help` — command reference

## Installed skills location

Skills are installed to `<sygen_home>/workspace/skills/<name>/`. They follow the standard SKILL.md format and are synced across CLI providers via the skill sync system (see `skill_system.md`).
