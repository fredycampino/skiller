# Skiller

Declarative runtime for small operational workflows.

`skiller` runs YAML-defined agents and workflow files with a simple execution loop, built-in persistence, MCP tool calls, and webhook-based resume. It is designed for flows that need to mix deterministic steps, external tools, and waiting states without turning the whole system into ad hoc glue code.

Current step types:
- `agent`
- `assign`
- `send`
- `notify`
- `shell`
- `mcp`
- `switch`
- `wait_channel`
- `wait_input`
- `when`
- `wait_webhook`

## Why It Exists

`skiller` gives you a small runtime for flows like:
- call an external tool
- store the result
- branch on it
- wait for an external event
- resume from persistence

The core model is intentionally small:
- internal catalog entries live in `packages/skiller/agents/<id>/agent.yaml`
- external workflow files can be run with `skiller run --file <path>`
- the runtime snapshots the selected definition into the DB when a run starts
- each step decides the next transition
- waiting is persisted, not simulated in memory

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run an internal catalog agent:

```bash
skiller run ant
```

Persistent configuration lives outside the current working directory:

```text
~/.skiller/settings/config.json
```

Use `AGENT_CONFIG_FILE=/path/to/config.json` to point Skiller at another JSON config.
Environment variables override the JSON file for one-off runs. Skiller does not load `.env` files.
See [`packages/skiller/docs/config/config.md`](packages/skiller/docs/config/config.md) for the full JSON format.

Run an external workflow file:

```bash
skiller run --file skills/story_router.yaml --arg path=cave --arg mood=curious
```

Inspect a run:

```bash
skiller status <run_id>
skiller logs <run_id>
skiller delete <run_id>
```

`delete` removes the run and database rows tied to it, including runtime events, waits,
external event records, deduplication receipts for those events, and persisted output bodies.

Run a workflow file directly:

```bash
skiller run --file skills/notify_test.yaml
```

## Example Internal Catalog Entry

```yaml
name: ant
description: "Terminal agent chat with tool access"
version: "0.1"
start: ask_user

inputs: {}

steps:
  - wait_input: ask_user
    prompt: "Write a message. Type exit, quit, or bye to stop."
    next: decide_exit

  - switch: decide_exit
    value: '{{output_value("ask_user").payload.text}}'
    cases:
      exit: done
      quit: done
      bye: done
    default: support_agent

  - agent: support_agent
    system: |
      You are a helpful assistant in a terminal chat.
      Reply in the same language as the user.
      Be concise, clear, and direct.
      Use tools only when they genuinely help.
    task: '{{output_value("ask_user").payload.text}}'
    tools:
      - notify
      - shell
    max_turns: 10
    next: ask_user

  - notify: done
    message: "Chat closed."
```

Run it with:

```bash
skiller run ant
```

## What The Runtime Supports

### Deterministic steps

- `assign`
- `notify`
- `switch`
- `when`

### Runtime-mediated steps

- `agent`
- `send`

### External execution

- `shell`
- `mcp`

### Persistent waiting

- `wait_channel`
- `wait_input`
- `wait_webhook`

This makes it possible to build flows such as:

```text
notify -> shell -> when -> wait_input -> notify
```

## MCP

`mcp` is the main extension point for external tools.

Minimal examples already in the repo:
- [`skills/stdio_mcp_test.yaml`](skills/stdio_mcp_test.yaml)
- [`skills/http_mcp_test.yaml`](skills/http_mcp_test.yaml)
- [`packages/skiller/agents/pr/agent.yaml`](packages/skiller/agents/pr/agent.yaml)

The source of truth for MCP connection settings lives in the selected YAML definition under `mcp:`.
For the internal GitHub PR flow, [`packages/skiller/agents/pr/agent.yaml`](packages/skiller/agents/pr/agent.yaml) uses:

- URL: `https://api.githubcopilot.com/mcp/`
- Token: `~/.skiller/secrets/github_mcp_token`

## Webhooks And Waiting

`wait_channel`, `wait_webhook`, and `wait_input` are first-class runtime primitives:
- the run moves to `WAITING`
- the current step stays on the same waiting step
- a matching webhook event or input event resolves the wait
- the run resumes from persisted state

Basic operations:

```bash
skiller input receive <run_id> --text "database timeout"
skiller webhook register github-ci
skiller webhook receive github-ci 42 --json '{"ok": true}' --dedup-key demo-1
skiller resume <run_id>
```

You can also start the local server automatically when a run ends in `WAITING`:

```bash
skiller run --file packages/skiller/tests/e2e/skills/wait_webhook_cli_e2e.yaml --arg key=42 --start-server
```

Operational tooling:

```bash
skiller server start
skiller server status
skiller server stop

skiller cloudflared login start
skiller cloudflared ensure --domain <domain>
skiller cloudflared start
```

## Project Layout

- `packages/skiller/src/skiller`: product runtime and CLI code
- `packages/skiller/agents`: internal catalog entries resolved by `skiller run <id>`
- `apps/tui`: extracted Textual UI app (`stui`)
- `skills`: external examples, demos, and legacy/manual test fixtures
- `packages/skiller/docs`: runtime and CLI documentation
- `packages/skiller/tests`: runtime, CLI, and shared verification

## Documentation

Core guides:
- [`packages/skiller/docs/cli/command-guide.md`](packages/skiller/docs/cli/command-guide.md)
- [`packages/skiller/docs/cli/tool-server.md`](packages/skiller/docs/cli/tool-server.md)
- [`packages/skiller/docs/cli/tool-cloudflared.md`](packages/skiller/docs/cli/tool-cloudflared.md)
- [`packages/skiller/docs/skills/skill-schema.md`](packages/skiller/docs/skills/skill-schema.md)
- [`packages/skiller/docs/db/schema.md`](packages/skiller/docs/db/schema.md)
- [`packages/skiller/docs/runtime/execution-model.md`](packages/skiller/docs/runtime/execution-model.md)
- [`packages/skiller/docs/steps/mcp.md`](packages/skiller/docs/steps/mcp.md)
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

Manual CLI E2E flows live in `packages/skiller/tests/e2e/cli_*.sh`. Use them when you need to exercise the real CLI path without mixing those checks into the default `pytest` suite.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

## Disclaimer

This project is provided "as is", without warranties of any kind. The authors and
contributors are not responsible for production incidents, data loss, service
interruptions, security issues, regulatory non-compliance, third-party integration
failures, or any direct or indirect damages resulting from its use.
