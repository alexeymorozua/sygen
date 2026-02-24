# supervisor (`ductor_bot/run.py`)

Optional local supervisor for development-style process restarts.

## Purpose

`ductor` normally starts `ductor_bot.__main__:main` directly.

`ductor_bot/run.py` is an extra process wrapper that:

- starts `python -m ductor_bot` as a child process,
- watches Python file changes (when `watchfiles` is installed),
- restarts the child on crash or explicit restart exit code.

## Child lifecycle

Supervisor behavior in `supervisor()`:

1. sets `DUCTOR_SUPERVISOR=1`,
2. spawns child process,
3. waits for one of:
   - child exit,
   - file change trigger (hot-reload path),
4. applies restart policy.

## Restart policy

- exit code `0`: clean shutdown, supervisor exits
- exit code `42`: immediate restart (`EXIT_RESTART`)
- file change (`*.py` under `ductor_bot/`): immediate restart
- other non-zero exit: exponential backoff restart
  - fast-crash threshold: `<10s`
  - max backoff: `30s`

## Signal handling

- supervisor sends `SIGTERM` to child first
- waits up to `10s`
- escalates to `SIGKILL` if needed

On POSIX, `SIGINT`/`SIGTERM` are wired to cancel the supervisor task.

## When to use

Use the supervisor only when you explicitly want restart/backoff + optional hot-reload behavior around the normal bot entrypoint.
