# Skiller.run

Run and resume agents and flows.

Skiller runs declarative YAML workflows with deterministic steps, persisted waiting
states, resumable execution, and full log-event observability.

## What It Does

- run YAML-defined agents and workflows
- resume flows from persisted waiting states
- execute deterministic workflow steps
- keep full observability with log events
- inspect and manage persisted runs

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Usage

### CLI to run agents and workflows

Use `skiller` when you want the direct command-line runtime.

Run the bundled terminal agent:

```bash
skiller run mono
```

Run a YAML workflow definition:

```bash
skiller run --file <path>
```

Inspect and manage runs:

```bash
skiller status <run_id>
skiller logs <run_id>
skiller delete <run_id>
```

`delete` removes the run and database rows tied to it, including runtime events,
waits, external event records, deduplication receipts for those events, and
persisted output bodies.

Resume a waiting run:

```bash
skiller input receive <run_id> --text "hello"
skiller resume <run_id>
```

### STUI for chat and launch runs

Use `stui` when you want an interactive terminal UI to chat, launch runs, and
manage persisted runs.

```bash
stui
```

## Configuration

Agent configuration is selected in this order:

1. `AGENT_AGENT_CONFIG_FILE`
2. `agent.json` next to the selected `agent.yaml`
3. `~/.skiller/settings/agent.json`

General runtime configuration lives in:

```text
~/.skiller/settings/config.json
```

Skiller does not load `.env` files.

See:

- [`packages/skiller/docs/agent/agent-config.md`](packages/skiller/docs/agent/agent-config.md)
- [`packages/skiller/docs/config/config.md`](packages/skiller/docs/config/config.md)

## Workflow Steps

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
The workflow is intentionally small:

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
- [`packages/skiller/docs/skills/skill-schema.md`](packages/skiller/docs/skills/skill-schema.md)
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
