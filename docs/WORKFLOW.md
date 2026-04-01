# Workflow Engine

YAML-defined multi-agent pipelines with conditions, retries, and user interaction.

## Quick Start

1. Enable in `config.json`:
```json
{
  "workflow": {
    "enabled": true,
    "max_parallel_runs": 5,
    "default_step_timeout": 3600.0
  }
}
```

2. Create a YAML file in `~/.sygen/workflows/`:
```yaml
id: hello
name: Hello World
trigger:
  manual: true
variables:
  greeting: "Hi there"
steps:
  - id: greet
    type: notify
    message: "$greeting! Workflow started."
  - id: ask_user
    type: wait_for_reply
    message: "What would you like me to do?"
  - id: process
    type: ask_agent
    agent: main
    prompt: "User said: $steps.ask_user.output — help them."
  - id: done
    type: notify
    message: "Done! Result: $steps.process.output"
```

3. Run it:
```
/workflow run hello
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/workflow` or `/workflow list` | List all workflow definitions |
| `/workflow runs` | List active/recent runs |
| `/workflow run <id>` | Start a workflow |
| `/workflow run <id> --var key=val` | Start with variable overrides |
| `/workflow status <run_id>` | Show detailed run status |
| `/workflow cancel <run_id>` | Cancel a running/waiting workflow |

## Step Types

### `ask_agent`

Send a prompt to an agent and capture its response.

```yaml
- id: research
  type: ask_agent
  agent: researcher        # target agent name
  prompt: "Find info about $topic"
  timeout: 300             # seconds (default: 3600)
  new_session: true        # start fresh session (default: true)
  provider: claude         # optional provider override
  model: opus              # optional model override
```

### `notify`

Send a message to the user's chat. Does not wait for a response.

```yaml
- id: update
  type: notify
  message: "Step completed: $steps.research.output"
```

### `wait_for_reply`

Send a message and pause the workflow until the user responds. The user's reply is stored in `$steps.<id>.output`.

```yaml
- id: confirm
  type: wait_for_reply
  message: "Proceed with the plan? (yes/no)"
```

> **Note:** While a workflow is waiting, all slash commands (`/workflow cancel`, `/stop`, etc.) still work. Only non-command messages are captured as the reply.

> **Note:** `wait_for_reply` cannot be used inside a `parallel` block.

### `condition`

Branch the workflow based on an expression.

```yaml
- id: check
  type: condition
  if: "'yes' == '$steps.confirm.output'"
  then: proceed_step
  else: cancel_step
```

Expressions are evaluated with a safe AST-based evaluator (no `eval()`). Supported: string comparisons (`==`, `!=`, `in`), boolean logic (`and`, `or`, `not`), and literals.

### `parallel`

Execute multiple steps concurrently.

```yaml
- id: gather
  type: parallel
  steps:
    - id: search_jira
      type: ask_agent
      agent: jira_agent
      prompt: "Find related tickets for $topic"
    - id: search_docs
      type: ask_agent
      agent: docs_agent
      prompt: "Find documentation for $topic"
```

Results are accessible via `$steps.search_jira.output` and `$steps.search_docs.output` in subsequent steps.

## Variables

### Definition variables

```yaml
variables:
  topic: "default value"
  max_results: "10"
```

Override at runtime: `/workflow run my_wf --var topic=AI --var max_results=5`

### Variable references in prompts

| Syntax | Resolves to |
|--------|-------------|
| `$topic` | Value from `variables` |
| `$variables.topic` | Same as above (explicit) |
| `$steps.research.output` | Output of step `research` |

## Flow Control

### Sequential (default)

Steps execute in order. Each step runs after the previous one completes.

### `goto`

Jump to a specific step after completion:

```yaml
- id: step_a
  type: notify
  message: "Jumping to step_c"
  goto: step_c

- id: step_b   # skipped
  type: notify
  message: "This won't run"

- id: step_c
  type: notify
  message: "Landed here"
```

### Condition branching

Use `condition` steps to branch (see above).

## Error Handling

Each step has an `on_error` strategy:

### `abort` (default)

Stop the workflow and mark it as failed:

```yaml
- id: critical
  type: ask_agent
  agent: main
  prompt: "Do something critical"
  on_error: abort
```

### `retry`

Retry the step with configurable attempts and delay:

```yaml
- id: flaky_call
  type: ask_agent
  agent: external_api
  prompt: "Call the API"
  on_error: retry
  retry:
    max_attempts: 3
    delay_seconds: 30
```

### `fallback`

Jump to a different step on failure:

```yaml
- id: primary
  type: ask_agent
  agent: fast_agent
  prompt: "Quick response"
  on_error: fallback
  fallback:
    goto: backup_step
```

### `skip`

Skip the failed step and continue to the next:

```yaml
- id: optional
  type: ask_agent
  agent: helper
  prompt: "Nice to have"
  on_error: skip
```

## HTTP API

When the internal API is running, workflow endpoints are available at `127.0.0.1:<port>`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workflows/list` | List definitions and runs |
| POST | `/workflows/run` | Start a workflow |
| GET | `/workflows/status?run_id=...` | Get run status |
| POST | `/workflows/cancel` | Cancel a run |

### Start a workflow via HTTP

```bash
curl -X POST http://127.0.0.1:8799/workflows/run \
  -H 'Content-Type: application/json' \
  -d '{"workflow_id": "hello", "chat_id": 123, "transport": "tg"}'
```

## File Observer

The engine watches `~/.sygen/workflows/` for changes. When you add, edit, or delete a YAML file, definitions are automatically reloaded within 5 seconds. No restart needed.

## Real-World Example: Watchface Pipeline

```yaml
id: watchface_pipeline
name: Watchface Creation
trigger:
  manual: true
variables:
  watch_model: ""
  style: ""
steps:
  - id: get_requirements
    type: wait_for_reply
    message: |
      What kind of watchface do you need?
      - Watch model?
      - Style (minimal, sport, classic)?
      - Any specific complications (weather, steps, heart rate)?

  - id: design
    type: ask_agent
    agent: designer
    prompt: |
      Create a watchface design for $watch_model.
      User requirements: $steps.get_requirements.output
      Style: $style
    timeout: 600

  - id: review
    type: wait_for_reply
    message: |
      Here's the design:
      $steps.design.output

      Approve? (yes / give feedback)

  - id: check_approval
    type: condition
    if: "'yes' in '$steps.review.output'.lower()"
    then: implement
    else: revise

  - id: revise
    type: ask_agent
    agent: designer
    prompt: |
      Revise the design based on feedback:
      $steps.review.output
      Original design: $steps.design.output
    goto: review

  - id: implement
    type: parallel
    steps:
      - id: code_xml
        type: ask_agent
        agent: developer
        prompt: "Implement the watchface XML: $steps.design.output"
      - id: generate_assets
        type: ask_agent
        agent: asset_gen
        prompt: "Generate PNG assets for: $steps.design.output"

  - id: done
    type: notify
    message: |
      Watchface ready!
      XML: $steps.code_xml.output
      Assets: $steps.generate_assets.output
```
