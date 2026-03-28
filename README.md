# Skiller

Declarative runtime for small operational workflows.

`skiller` runs YAML-defined skills with a simple execution loop, built-in persistence, MCP tool calls, and webhook-based resume. It is designed for flows that need to mix deterministic steps, external tools, and waiting states without turning the whole system into ad hoc glue code.

Current step types:
- `assign`
- `notify`
- `llm_prompt`
- `mcp`
- `switch`
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
- skills live in `skills/*.yaml`
- the runtime snapshots a skill into the DB when a run starts
- each step decides the next transition
- waiting is persisted, not simulated in memory

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run a minimal skill:

```bash
skiller run notify_test
```

Run a demo with branching:

```bash
skiller run story_router --arg path=cave --arg mood=curious
```

Inspect a run:

```bash
skiller status <run_id>
skiller logs <run_id>
```

Run a skill file directly:

```bash
skiller run --file skills/notify_test.yaml
```

## Example Skill

```yaml
name: notify_test
description: "Minimal single-step notify test"
version: "0.1"

inputs: {}

steps:
  - id: start
    type: notify
    message: "notify smoke ok"
```

Run it with:

```bash
skiller run notify_test
```

## What The Runtime Supports

### Deterministic steps

- `assign`
- `notify`
- `switch`
- `when`

### External execution

- `llm_prompt`
- `mcp`

### Persistent waiting

- `wait_input`
- `wait_webhook`

This makes it possible to build flows such as:

```text
notify -> mcp -> when -> wait_input -> notify
```

## MCP

`mcp` is the main extension point for external tools.

Minimal examples already in the repo:
- [`skills/stdio_mcp_test.yaml`](/home/fede/develop/py/skiller/skills/stdio_mcp_test.yaml)
- [`skills/http_mcp_test.yaml`](/home/fede/develop/py/skiller/skills/http_mcp_test.yaml)
- [`skills/pull_request.yaml`](/home/fede/develop/py/skiller/skills/pull_request.yaml)

The source of truth for MCP connection settings lives in the skill YAML under `mcp:`.

## Webhooks And Waiting

`wait_webhook` and `wait_input` are first-class runtime primitives:
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

You can also start webhooks automatically when a run ends in `WAITING`:

```bash
skiller run --file tests/e2e/skills/wait_webhook_cli_e2e.yaml --arg key=42 --start-webhooks
```

## Project Layout

- `src/skiller`: application code
- `skills`: internal YAML skills
- `docs`: technical documentation
- `tests`: automated and manual verification

## Documentation

Core guides:
- [`docs/cli/command-guide.md`](/home/fede/develop/py/skiller/docs/cli/command-guide.md)
- [`docs/guia_creacion_skills.md`](/home/fede/develop/py/skiller/docs/guia_creacion_skills.md)
- [`docs/steps/mcp.md`](/home/fede/develop/py/skiller/docs/steps/mcp.md)
- [`docs/steps/wait_input.md`](/home/fede/develop/py/skiller/docs/steps/wait_input.md)
- [`docs/steps/wait_webhook.md`](/home/fede/develop/py/skiller/docs/steps/wait_webhook.md)

Step references:
- [`docs/steps/assign.md`](/home/fede/develop/py/skiller/docs/steps/assign.md)
- [`docs/steps/llm_prompt.md`](/home/fede/develop/py/skiller/docs/steps/llm_prompt.md)
- [`docs/steps/notify.md`](/home/fede/develop/py/skiller/docs/steps/notify.md)
- [`docs/steps/switch.md`](/home/fede/develop/py/skiller/docs/steps/switch.md)
- [`docs/steps/when.md`](/home/fede/develop/py/skiller/docs/steps/when.md)

## Development

Run the main checks:

```bash
./.venv/bin/python -m ruff check src tests scripts/ci
./.venv/bin/python -m pytest
./.venv/bin/python -m build --no-isolation
```

Manual CLI E2E flows live in `tests/e2e/cli_*.sh`. Use them when you need to exercise the real CLI path without mixing those checks into the default `pytest` suite.

## License

Apache-2.0. See [`LICENSE`](/home/fede/develop/py/skiller/LICENSE).

## Disclaimer

This project is provided "as is", without warranties of any kind. The authors and
contributors are not responsible for production incidents, data loss, service
interruptions, security issues, regulatory non-compliance, third-party integration
failures, or any direct or indirect damages resulting from its use.
