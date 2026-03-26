# Memory System

Sygen uses a **modular memory** system. Memory is split into focused modules
under `memory_system/modules/`, indexed by `MAINMEMORY.md`.

## Silence Is Mandatory

Never tell the user you are reading or writing memory.
Memory operations are invisible.

## Structure

- `MAINMEMORY.md` — Module Index only (table with links) + SHARED KNOWLEDGE block
- `modules/` — separate files by role:
  - `user.md` — **Always Load**: user profile, projects, communication style
  - `decisions.md` — **Always Load**: preferences, settings, agent behavior rules
  - `infrastructure.md`, `tools.md`, `crons.md` — **On Demand** by topic

## Read First

At session start, the system auto-injects Always Load modules (`user.md`, `decisions.md`).
For on-demand modules, read them when the request matches their topic.

## When to Write

- Durable personal facts or preferences
- Decisions that should affect future behavior
- User explicitly asks to remember
- Repeating workflow patterns
- Cron/webhook setup signals that imply interests

## When Not to Write

- One-off throwaway requests
- Temporary debugging noise
- Facts already recorded

## Format Rules

- Each module ≤ 80 lines; when full — clean old/stale entries first
- Keep entries short and actionable
- Use `YYYY-MM-DD` timestamps
- Merge duplicates and remove stale facts
- Do not put content directly into MAINMEMORY.md — use modules

## Shared Knowledge (SHAREDMEMORY.md)

When you learn something relevant to ALL agents (server facts, user preferences,
infrastructure changes, shared conventions), update shared knowledge:

```bash
python3 tools/agent_tools/edit_shared_knowledge.py --append "New shared fact"
```

The Supervisor automatically syncs SHAREDMEMORY.md into every agent's MAINMEMORY.md.
Agent-specific knowledge stays in your own memory modules.

## Cleanup Rules

- If user says data is wrong or should be forgotten, remove/update immediately
- Do not leave "deleted" markers; keep files clean
- Periodically review modules for stale entries
