# Workflow Engine — Implementation Plan

**Status:** Planned (not started)
**Estimated:** ~3,250 lines of code, 4 phases
**Priority:** When real use cases accumulate (watchface pipeline is first candidate)

## Architecture

Workflow Engine sits alongside Cron, Background, and Task subsystems. Reuses same patterns:
- JSON persistence via `atomic_json_save`/`load_json`
- Delivery through `MessageBus`/`Envelope` pipeline
- Step execution through `InterAgentBus.send` and `TaskHub.submit`
- Telegram commands in `CommandRegistry`

## YAML Schema Example

```yaml
id: watchface_pipeline
name: Watchface Creation Pipeline
trigger:
  cron: ""
  manual: true
variables:
  style: "modern"
steps:
  - id: design
    type: ask_agent
    agent: designer
    prompt: "Create a watchface design with style=$style"
    timeout: 1800

  - id: implement
    type: ask_agent
    agent: developer
    prompt: "Implement this design: $steps.design.output"
    retry: { max_attempts: 2, delay_seconds: 30 }
    on_error: fallback
    fallback: { goto: design }

  - id: build
    type: ask_agent
    agent: developer
    prompt: "Build, emulate, screenshot: $steps.implement.output"

  - id: show_user
    type: notify
    message: "Screenshots ready: $steps.build.output"

  - id: approval
    type: wait_for_reply
    prompt: "Approve? (yes/no/feedback)"
    timeout: 86400

  - id: decide
    type: condition
    if: "'yes' in $steps.approval.output.lower()"
    then: publish
    else: iterate

  - id: iterate
    type: ask_agent
    agent: designer
    prompt: "Revise based on: $steps.approval.output"
    goto: implement

  - id: publish
    type: ask_agent
    agent: developer
    prompt: "Publish the watchface"
```

## New Files

### Core: `sygen_bot/workflow/`

| File | Purpose | Lines |
|------|---------|-------|
| `__init__.py` | Exports | 15 |
| `models.py` | Pydantic models (WorkflowDefinition, WorkflowRun, StepDefinition, etc.) | 280 |
| `registry.py` | YAML loading, JSON persistence | 220 |
| `engine.py` | Execution loop, control flow, variable context | 450 |
| `executor.py` | Step type executors (ask_agent, notify, wait_for_reply, condition, parallel) | 300 |
| `variables.py` | Template resolution ($steps.X.output, $variables.Y) | 120 |
| `observer.py` | Lifecycle, file-watching for YAML changes | 180 |
| `manager.py` | CRUD for definitions and runs | 200 |
| `commands.py` | `/workflow` Telegram command handler | 150 |

### CLI Tools: `tools/workflow_tools/`

| File | Purpose | Lines |
|------|---------|-------|
| `run_workflow.py` | Trigger workflow from CLI | 60 |
| `list_workflows.py` | List available/running | 50 |
| `cancel_workflow.py` | Cancel running workflow | 45 |
| `workflow_status.py` | Detailed status | 55 |

### Integration Points

| File | Change |
|------|--------|
| `workspace/paths.py` | Add `workflows_dir`, `workflow_runs_path` |
| `config.py` | Add `WorkflowConfig` (enabled, max_parallel_runs, timeouts) |
| `bus/envelope.py` | Add `Origin.WORKFLOW_RESULT`, `Origin.WORKFLOW_WAIT` |
| `bus/adapters.py` | Add `from_workflow_result()`, `from_workflow_wait()` |
| `orchestrator/core.py` | Wire `/workflow` command, `wait_for_reply` routing hook |
| `orchestrator/observers.py` | Add `WorkflowEngine` to lifecycle |
| `multiagent/internal_api.py` | Add `/workflows/*` HTTP endpoints |

### Tests: `tests/workflow/`

| File | Lines |
|------|-------|
| `test_models.py` | 150 |
| `test_variables.py` | 120 |
| `test_registry.py` | 100 |
| `test_engine.py` | 300 |
| `test_executor.py` | 200 |
| `test_commands.py` | 80 |

## Step Types

| Type | Description |
|------|-------------|
| `ask_agent` | Sync call to agent via InterAgentBus, waits for response |
| `notify` | Send message to user via MessageBus |
| `wait_for_reply` | Pause workflow, serialize state, resume on user reply |
| `condition` | Evaluate expression, branch to `then`/`else` step |
| `parallel` | Run multiple sub-steps concurrently |
| `script` | Run shell command (future) |

## Error Handling

| Strategy | Behavior |
|----------|----------|
| `abort` (default) | Stop workflow, notify user |
| `retry` | Re-execute up to N times with delay |
| `fallback` | Jump to specified step ID |
| `skip` | Mark skipped, continue |

## `wait_for_reply` Mechanism

1. Engine sends notification to user with prompt
2. Serializes run state to JSON, sets `status=waiting`
3. asyncio task completes (returns)
4. On user message: `Orchestrator._route_message()` checks for waiting workflows
5. If found: routes to `engine.resume_workflow(run_id, user_text)`
6. Engine creates new asyncio task, continues from next step

Survives bot restarts (state on disk).

## Telegram Commands

| Command | Action |
|---------|--------|
| `/workflow` | List definitions + active runs |
| `/workflow run <id> [--var key=val]` | Start workflow |
| `/workflow status <run_id>` | Detailed status |
| `/workflow cancel <run_id>` | Cancel |
| `/workflow runs` | List active runs |

## Implementation Phases

### Phase 1: Core (models + registry + variables)
1. `sygen_bot/workflow/__init__.py`
2. `sygen_bot/workflow/models.py`
3. `sygen_bot/workflow/variables.py`
4. `sygen_bot/workflow/registry.py`
5. Add paths to `SygenPaths`
6. Tests: `test_models`, `test_variables`, `test_registry`

### Phase 2: Engine + executors
7. `sygen_bot/workflow/executor.py`
8. `sygen_bot/workflow/engine.py`
9. Tests: `test_executor`, `test_engine`

### Phase 3: Integration
10. `WorkflowConfig` in `config.py`
11. `Origin.WORKFLOW_*` in `envelope.py`
12. Bus adapters
13. `observer.py`
14. `commands.py`
15. Wire into Orchestrator, ObserverManager, InternalAPI

### Phase 4: CLI tools + polish
16. `tools/workflow_tools/` scripts
17. `test_commands.py`
18. i18n strings
19. Documentation (RULES templates)

## Key Design Decisions

1. **Separate package** (`sygen_bot/workflow/`), not inside `orchestrator/`
2. **Sync `InterAgentBus.send()`** for steps (engine already runs in background)
3. **Disk serialization** for `wait_for_reply` (survives restarts)
4. **Safe expression evaluator** for conditions (no `eval()`)
5. **MessageBus delivery** for notifications (same pipeline as cron/tasks)
