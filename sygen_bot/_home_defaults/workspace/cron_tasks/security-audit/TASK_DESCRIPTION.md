You are a security audit agent. Check for common security issues in the agent environment.

## Steps

### 1. Check sensitive file permissions

Verify these files exist and have correct permissions (600):
- `~/.sygen/.env`
- `~/.sygen/agents.json`

Use `stat` to check permissions. If a file doesn't exist, note it but don't treat it as a critical issue (it may not be configured yet).

If permissions are wrong, fix them:
```bash
chmod 600 ~/.sygen/.env
chmod 600 ~/.sygen/agents.json
```

### 2. Scan for leaked secrets in workspace files

Scan files with extensions: .py, .md, .json, .sh, .toml, .yaml, .yml
In these directories:
- `~/.sygen/workspace/`
- `~/.sygen/agents/*/workspace/` (discover agents via `ls ~/.sygen/agents/`)

Search for these patterns:
- GitHub tokens: `ghp_[A-Za-z0-9]{36}`
- OpenAI/Anthropic API keys: `sk-[A-Za-z0-9]{20,}`
- Google API keys: `AIza[A-Za-z0-9_-]{35}`
- Telegram bot tokens: `[0-9]{8,10}:AA[A-Za-z0-9_-]{33}`
- AWS access keys: `AKIA[A-Z0-9]{16}`
- Generic high-entropy strings assigned to variables named `token`, `secret`, `password`, `api_key` (use judgment)

**Exclude from scanning:**
- `~/.sygen/.env` (secrets belong there)
- `~/.sygen/agents.json` (tokens belong there)
- This task's own TASK_DESCRIPTION.md (contains the patterns as examples)
- Any file inside `cron_tasks/security-audit/`

Use `grep` or read files directly. Do NOT use the `requests` library or make any HTTP calls.

### 3. Check disk usage

Run `df -h /` and check if usage exceeds 90%. If so, warn.

### 4. Check logs directory size

Check the size of `~/.sygen/logs/`:
```bash
du -sh ~/.sygen/logs/
```
Warn if it exceeds 500MB.

### 5. Report

If ALL checks pass with no issues:
Reply with exactly `[SILENT]` and nothing else. This suppresses delivery to the user.

If issues were found, report them clearly:

```
Security audit — issues found:

⚠️ Permissions:
- ~/.sygen/.env had permissions 644, fixed to 600

🔴 Leaked secrets:
- workspace/tools/example.py:15 — possible GitHub token (ghp_...)

⚠️ Disk:
- Root filesystem at 92% usage

⚠️ Logs:
- ~/.sygen/logs/ is 750MB, consider cleanup
```

Only report actual findings. Do not include checks that passed.
