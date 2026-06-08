# Skiller.run

**A runtime for agentic workflows.**

Skiller runs agentic flows as durable executions with persistent state, safe resume, and full observability logs.

## What It Does

- Runs durable YAML flows that can include agents
- Pauses and resumes flows from persisted waiting states
- Provides CLI to observe and manage persisted runs
- Includes a TUI for chatting with agents, launching flows, and managing runs

```yaml
name: mono
description: "Terminal agent chat with shell and file access"
version: "0.1"
start: ask_user

inputs: {}

steps:
  - wait_input: ask_user
    prompt: "Write a task or message. Type exit, quit, or bye to stop."
    next: decide_exit

  - switch: decide_exit
    value: '{{output_value("ask_user").payload.text}}'
    cases:
      exit: done
      quit: done
      bye: done
    default: mono_agent

  - agent: mono_agent
    system:
      file: "./system.md"
    task: '{{output_value("ask_user").payload.text}}'
    tools:
      - shell
      - files
    max_turns: 50
    next: ask_user

  - assign: done
    values:
      status: "closed"
```

## Install
For regular CLI usage, install it with `pipx`:

```bash
pipx install skiller
```

## STUI for chat and launch runs

Use `skiller` when you want an interactive terminal UI to chat, launch runs, and
manage persisted runs.

```bash
skiller
```

### Use CLI to run flows

Run a YAML flow definition:

```bash
skiller run --file <path>
```
Inspect and manage runs:

```bash
skiller status <run_id>
skiller logs <run_id>
skiller delete <run_id>
```

## Flow Steps

Deterministic:

- `assign`
- `notify`
- `switch`
- `when`

Execution:

- `agent`
- `shell`

Waiting:

- `wait_input`
- `wait_webhook`

## Persistence

Skiller persists:

- run state
- step outputs
- runtime log events
- waiting states
- external event receipts
- persisted output bodies

Waiting is persisted, not simulated in memory. A run can stop in `WAITING` and
resume later from stored state.

## How Mono Is Built

`mono` is a regular YAML-defined agent with local runtime configuration beside it.
The flow is intentionally small:

- wait for terminal input with `wait_input`
- stop on `exit`, `quit`, or `bye` with `switch`
- send every other message to an `agent` step
- let that agent use its configured `shell` and `files` tools
- loop back to `wait_input`

Minimal shape:

```yaml
name: mono
start: ask_user

steps:
  - wait_input: ask_user
    next: decide_exit

  - switch: decide_exit
    default: support_agent

  - agent: support_agent
    tools:
      - shell
      - files
    next: ask_user
```

The full prompt and step definition live in
[`packages/skiller/agents/mono/agent.yaml`](packages/skiller/agents/mono/agent.yaml).
The provider, loop limits, shell allowlist, and file roots live in
[`packages/skiller/agents/mono/agent.json`](packages/skiller/agents/mono/agent.json).

## Project Layout

- `packages/skiller/src/skiller`: runtime and CLI code
- `packages/skiller/agents/mono`: bundled terminal agent
- `packages/skiller/docs`: runtime and CLI documentation
- `packages/skiller/tests`: runtime, CLI, and integration tests
- `apps/tui`: Textual UI app

## Documentation

Core guides:

- [`packages/skiller/docs/cli/command-guide.md`](packages/skiller/docs/cli/command-guide.md)
- [`packages/skiller/docs/flows/flow-schema.md`](packages/skiller/docs/flows/flow-schema.md)
- [`packages/skiller/docs/db/schema.md`](packages/skiller/docs/db/schema.md)
- [`packages/skiller/docs/runtime/execution-model.md`](packages/skiller/docs/runtime/execution-model.md)
- [`packages/skiller/docs/steps/agent.md`](packages/skiller/docs/steps/agent.md)
- [`packages/skiller/docs/steps/wait_input.md`](packages/skiller/docs/steps/wait_input.md)
- [`packages/skiller/docs/steps/wait_webhook.md`](packages/skiller/docs/steps/wait_webhook.md)

Step references:

- [`packages/skiller/docs/steps/assign.md`](packages/skiller/docs/steps/assign.md)
- [`packages/skiller/docs/steps/shell.md`](packages/skiller/docs/steps/shell.md)
- [`packages/skiller/docs/steps/notify.md`](packages/skiller/docs/steps/notify.md)
- [`packages/skiller/docs/steps/switch.md`](packages/skiller/docs/steps/switch.md)
- [`packages/skiller/docs/steps/when.md`](packages/skiller/docs/steps/when.md)

## Development

Run the main checks:

```bash
./.venv/bin/python -m ruff check packages/skiller/src apps/tui/src packages/skiller/tests apps/tui/tests
./.venv/bin/python -m pytest packages/skiller/tests apps/tui/tests
./.venv/bin/python -m build --no-isolation
```

Manual CLI E2E flows live in `packages/skiller/tests/e2e/cli_*.sh`. Use them
when you need to exercise the real CLI path without mixing those checks into the
default `pytest` suite.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

## Disclaimer

This project is provided "as is", without warranties of any kind. The authors and
contributors are not responsible for production incidents, data loss, service
interruptions, security issues, regulatory non-compliance, third-party integration
failures, or any direct or indirect damages resulting from its use.
