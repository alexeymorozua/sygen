# Skill Marketplace (ClawHub)

Browse, search, and install community skills from [OpenClaw's ClawHub](https://github.com/openclaw/skills) registry — with two-layer security scanning before every installation.

## Quick start

1. Enable in `config.json`:
   ```json
   {
     "skill_marketplace": {
       "enabled": true
     }
   }
   ```
2. Restart the bot (`/restart` or `touch ~/.sygen/restart-requested`).
3. Use `/skill search <query>` to find skills.

## Commands

| Command | Description |
|---|---|
| `/skill search <query>` | Search ClawHub registry. Results are paginated (5 per page) with ← Prev / Next → buttons. |
| `/skill install <name>` | Download a skill, run security scan, show report, and ask for confirmation. |
| `/skill list` | List all installed marketplace skills. |
| `/skill remove <name>` | Remove an installed skill. |
| `/skill help` | Show command reference. |

## How it works

### Searching

`/skill search` queries the GitHub API against the `openclaw/skills` repository. Results show skill name, author, and description with an **Install** button for each.

If there are more than 5 results, pagination buttons appear at the bottom. You can also browse the full catalog at [github.com/openclaw/skills](https://github.com/openclaw/skills) and then install by name.

### Installing

When you run `/skill install <name>` (or tap an Install button), the following happens:

1. **Download** — the skill is downloaded to a temporary directory from GitHub.
2. **Security scan** — two-layer analysis runs automatically (see below).
3. **Report** — a scan report is shown with findings, if any.
4. **Your decision** — you see buttons to confirm or cancel:
   - If clean: ✅ **Install** / ❌ **Cancel**
   - If issues found: ❌ **Cancel** / ⚠️ **Install anyway**
5. **Installation** — on confirmation, the skill is copied to `~/.sygen/workspace/skills/<name>/`.

### After installation

Installed skills are automatically synced to all CLI providers:

| Provider | Location |
|---|---|
| Sygen workspace | `~/.sygen/workspace/skills/<name>/` |
| Claude Code | `~/.claude/skills/<name>/` |
| Codex CLI | `~/.codex/skills/<name>/` |
| Gemini CLI | `~/.gemini/skills/<name>/` |

Sync happens via symlinks (or copies in Docker mode) and is checked every 30 seconds.

## Security scanning

Every skill is scanned before installation. **The scan report is always shown to you.** Sygen does not silently install anything — you decide.

### Layer 1: Static analysis (always runs)

Regex pattern matching against all skill files:

**Critical patterns** (install blocked with warning):

| Pattern | Risk |
|---|---|
| `eval()` | Arbitrary code execution |
| `exec()` | Arbitrary code execution |
| `compile()` | Dynamic code compilation |
| `__import__()` | Dynamic module loading |
| `importlib` | Dynamic module loading |
| `marshal.loads` | Binary deserialization |
| `pickle.loads` | Unsafe deserialization |

**Warning patterns** (shown but does not block):

| Category | Patterns |
|---|---|
| Network calls | `curl`, `wget`, `requests`, `httpx`, `urllib`, `fetch`, `axios` |
| Sensitive paths | `~/.ssh/`, `~/.aws/`, `.env/`, `.git/config`, `wallet`, `keychain` |
| Code obfuscation | `base64.b64decode`, `codecs.decode` |
| Shell execution | `subprocess`, `os.system`, `os.popen`, `shlex` |
| Low-level access | `ctypes` |

### Layer 2: VirusTotal (optional)

If a VirusTotal API key is configured, each file's SHA-256 hash is checked against known malware signatures. Results show detection ratios (e.g., "2/72 engines flagged").

Free API keys are available at [virustotal.com](https://www.virustotal.com/) (4 requests/minute limit).

## Configuration

```json
{
  "skill_marketplace": {
    "enabled": true,
    "virustotal_api_key": "your-key-here"
  }
}
```

| Field | Default | Description |
|---|---|---|
| `enabled` | `false` | Must be `true` to use `/skill` commands. |
| `virustotal_api_key` | `null` | Optional. Enables VirusTotal hash scanning. |

## Risks and limitations

**Community skills are third-party code.** They are not reviewed or endorsed by Sygen. While security scanning catches common dangerous patterns, it cannot guarantee safety.

Specific risks:

- **Static analysis has limits.** Obfuscated code, indirect calls, or novel attack vectors may bypass pattern matching. The scanner catches common patterns, not all possible threats.
- **VirusTotal checks known malware only.** A clean VirusTotal result means the file hash is not in known malware databases — it does not prove the code is safe.
- **Skills run with agent permissions.** An installed skill has access to the agent's workspace, tools, and file system. A malicious skill could read, modify, or delete files.
- **No automatic updates.** Installed skills are static snapshots. If the author pushes a security fix, you need to reinstall manually.
- **Network-capable skills exist.** Skills with `requests`, `httpx`, or `curl` can make network calls. This is legitimate for many use cases (API integrations, web search) but could also exfiltrate data.

**Best practices:**

- Review the scan report carefully before installing.
- Enable VirusTotal for an additional layer of checking.
- Prefer skills from known authors or with many GitHub stars.
- Use `/skill list` periodically to review what is installed.
- Remove skills you no longer use with `/skill remove`.
- If in doubt, inspect the skill source on GitHub before installing.

## Files

| File | Description |
|---|---|
| `sygen_bot/skills/clawhub.py` | GitHub API client: search, download, install, list, remove |
| `sygen_bot/skills/scanner.py` | Security scanner: static analysis + VirusTotal |
| `sygen_bot/skills/commands.py` | `/skill` command handler with pagination and callbacks |

## Architecture

```text
User → /skill search <query>
    → GitHub API (openclaw/skills) → paginated results with Install buttons

User → /skill install <name>  (or taps Install button)
    → download to temp dir
    → SecurityScanner
        ├─ static analysis (7 critical + 13+ warning patterns)
        └─ VirusTotal API v3 (SHA-256 hash check, optional)
    → show scan report + confirm/cancel buttons
    → user confirms → install to workspace/skills/
    → auto-sync to ~/.claude/, ~/.codex/, ~/.gemini/
```
