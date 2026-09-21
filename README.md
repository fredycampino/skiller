# Skiller.run

**A runtime for agentic workflows.**

Skiller runs agentic flows as durable executions with persistent state, safe resume, and full observability logs.

## What It Does

Skiller turns a YAML flow into a durable execution. Define the work, start a run,
resume it when new input arrives, and inspect every step along the way.

1. **Define the flow.** Combine agents, tools, deterministic steps, and external
   input in YAML. With an [LLM provider](packages/skiller/docs/agent/agent-config-llm.md)
   and [tool policies](packages/skiller/docs/agent/agent-config-tools.md) configured,
   this two-step flow runs an ongoing agent session:

```yaml
name: mono
start: ask_user

steps:
  - wait_input: ask_user
    prompt: "What should the agent do?"
    next: mono_agent

  - agent: mono_agent
    system: |
      Complete the user's task and report the result clearly.
    task: '{{output_value("ask_user").payload.text}}'
    tools:
      - shell
      - files
    next: ask_user
```

2. **Start a durable run.** Skiller persists its state, outputs, and runtime
   events instead of keeping the execution only in memory.

```bash
skiller run ./mono.yaml
```

3. **Resume when input arrives.** Waiting state survives process restarts. Send
   input later and continue the same run from the exact step where it paused.

```bash
skiller input receive <run_id> --text "Audit the dependencies" --wait
```

4. **Observe and manage the run.** Check its current state, stream new events,
   or inspect the complete persisted history.

```bash
skiller status <run_id>
skiller observe <run_id>
skiller logs <run_id>
```

Prefer an interactive experience? Open the TUI to chat with agents, launch
flows, and return to previous runs:

```bash
skiller
```

## Install
For regular CLI usage, install it with `pipx`:

```bash
pipx install skiller
```

## Usage

### STUI: chat and launch runs

Use `skiller` when you want an interactive terminal UI to chat, launch runs, and
manage persisted runs.

```bash
skiller
```

### CLI: run and manage flows

Run a packaged, local, or configured flow reference:

```bash
skiller run @flows
skiller run @group/name
```

Direct paths are also supported:

```bash
skiller run ./my-flow.yaml
skiller run ~/flows/my-flow.yaml
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

## Project Layout

- `packages/skiller/src/skiller`: runtime and CLI code
- `apps/agents`: bundled agents and authentication flows
- `packages/skiller/docs`: runtime and CLI documentation
- `packages/skiller/tests`: runtime, CLI, and integration tests
- `apps/tui`: Textual UI app

## Dependencies

Runtime dependencies are grouped by the capability that uses them:

| Area | Dependencies | Used for |
| --- | --- | --- |
| Core | `pydantic`, `PyYAML` | Configuration validation and YAML flow loading |
| LLM providers | `openai`, `boto3` | OpenAI, Codex, and Amazon Bedrock adapters |
| MCP | `fastmcp` | MCP client connections and tool execution |
| Webhooks | `fastapi`, `uvicorn` | Local webhook server |
| Terminal UI | `textual` | Interactive agent chat and run management |

Development uses `pytest` for tests, `httpx` for HTTP test clients, and `ruff`
for linting. Packages are built with `hatchling`. Direct dependency constraints
live in [`pyproject.toml`](pyproject.toml); the resolved dependency graph lives in
[`uv.lock`](uv.lock).

## Documentation

Core guides:

- [`apps/instructions/skiller-user.md`](apps/instructions/skiller-user.md)
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

Manual CLI E2E flows live in `packages/skiller/tests/e2e/cli_*.sh`. Step-specific
flows live in `packages/skiller/tests/e2e-steps/<test>/run.sh`. Use them when you
need to exercise the real CLI path without mixing those checks into the default
`pytest` suite.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

## Disclaimer

This project is provided "as is", without warranties of any kind. The authors and
contributors are not responsible for production incidents, data loss, service
interruptions, security issues, regulatory non-compliance, third-party integration
failures, or any direct or indirect damages resulting from its use.
