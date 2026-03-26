# Main Memory

## Module Index

### Always Load
| Module | Description | Path |
|--------|-------------|------|
| user | User profile, projects, communication style | [modules/user.md](modules/user.md) |
| decisions | Decisions, preferences, settings, agent behavior | [modules/decisions.md](modules/decisions.md) |

### Load On Demand (by topic)
| Module | Description | Path |
|--------|-------------|------|
| infrastructure | Server, Telegram group, topics, CLI, sync | [modules/infrastructure.md](modules/infrastructure.md) |
| tools | Patches, tools, dependencies, update procedures | [modules/tools.md](modules/tools.md) |
| crons | All cron jobs and schedules | [modules/crons.md](modules/crons.md) |

### Identity (auto-injected)
Agent behavioral rules live in SHARED KNOWLEDGE below (managed by Supervisor, do not edit manually).

## How to Use

- Always read: `user.md` + `decisions.md`
- Determine topic of request → read the relevant on-demand module
- Before writing: check for duplicates, determine target module
- Each module ≤ 80 lines; when full — clean first, then write

--- SHARED KNOWLEDGE START ---
(Managed by Supervisor — do not edit manually.)
--- SHARED KNOWLEDGE END ---
