# CLI Command Guide

This guide documents the current `skiller` CLI commands and how they fit into the runtime flow.

See [`commands/catalogue.md`](commands/catalogue.md) for the command status catalogue.

Terminology used in this guide:
- transcript = the user-facing execution view rendered by the TUI
- `/logs` = the raw debug event stream

## Command Overview

### General

```bash
skiller --help
skiller --version
```

### Run lifecycle

```bash
skiller run <flow>
skiller run --file <flow.yaml>
skiller resume <run_id>
```

### Inspection

```bash
skiller status <run_id>
skiller runs [--limit N] [--status WAITING] [--status FAILED]
skiller logs <run_id>
skiller delete <run_id>
```

### Human input

```bash
skiller input receive <run_id> --text "..."
```

### Webhooks

```bash
skiller webhook register <webhook>
skiller webhook list
skiller webhook remove <webhook>
skiller webhook receive <webhook> <key> --json '{"ok": true}'
skiller webhook receive <webhook> <key> --json-file payload.json
```

### Worker operations

```bash
skiller worker start <run_id>
skiller worker run <run_id>
skiller worker resume <run_id>
```

### Agent control

```bash
skiller agent interrupt <run_id>
skiller agent stats <run_id> --agent <agent_id>
```

### Configuration

Skiller reads persistent config from `~/.skiller/settings/config.json`.
If `.env.development` exists in the current working directory, Skiller also reads
it after real environment variables and before JSON config files.
See [`../config/config.md`](../config/config.md).

### Cloudflared

```bash
skiller cloudflared login start
skiller cloudflared login status
skiller cloudflared login stop
skiller cloudflared ensure --domain <domain>
skiller cloudflared start
skiller cloudflared status
skiller cloudflared stop
```

### WhatsApp

```bash
skiller whatsapp pair start
skiller whatsapp pair status
skiller whatsapp pair stop

skiller whatsapp start
skiller whatsapp status
skiller whatsapp stop
```

## Typical Flows

## Run an agent

Command contract: [`commands/run.md`](./commands/run.md).

Internal agent:

```bash
skiller run ant
```

External file:

```bash
skiller run --file ./my-agent.yaml
```

With inputs:

```bash
skiller run pr --arg owner=my-org --arg repo=my-repo --arg head=feature/demo --arg base=main --arg title="demo" --arg body="demo body"
```

What it does:
- creates a run
- snapshots the agent definition into the database
- prepares and dispatches the worker
- returns the created `run_id`

## Inspect a run

Current run state:

```bash
skiller status <run_id>
```

Recent runs:

```bash
skiller runs
skiller runs --status WAITING
skiller runs --status FAILED --limit 50
```

Command contract: [`commands/runs.md`](./commands/runs.md).

Raw event log:

```bash
skiller logs <run_id>
```

Delete a run and all database rows tied to it:

```bash
skiller delete <run_id>
```

This is a destructive cleanup command. It removes the run, runtime events, waits, external
event records, deduplication receipts for those events, and persisted execution output bodies.

Rule of thumb:
- use `status` for current run state
- use `logs` when you need the raw event payloads

## Interrupt the current agent turn

Command contract: [`commands/agent.md`](./commands/agent.md).

```bash
skiller agent interrupt <run_id>
```

What it does:
- enqueues an `agent` steering item with action `abort_turn`
- does not cancel the run
- is consumed later by the agent loop at its steering checkpoints

## Inspect agent context stats

Command contract: [`commands/agent.md`](./commands/agent.md).

```bash
skiller agent stats <run_id> --agent <agent_id>
```

What it does:
- reads persisted context-window stats for the agent
- reports current window size, movement threshold, and configured capacity
- does not read or print the full context entries

## Resume a waiting run with text

```bash
skiller input receive <run_id> --text "database timeout"
```

What it does:
- persists the input event
- matches it against the waiting run
- marks the run resumable
- dispatches worker resume for matched runs

Command contract: [`commands/input.md`](./commands/input.md).

If needed, you can resume explicitly:

```bash
skiller resume <run_id>
```

Command contract: [`commands/resume.md`](./commands/resume.md).

Typical inspection flow:

```bash
skiller status <run_id>
skiller input receive <run_id> --text "database timeout"
skiller status <run_id>
```

## Resume a waiting run with a webhook

Register a webhook channel:

```bash
skiller webhook register github-ci
```

Deliver a payload:

```bash
skiller webhook receive github-ci 42 --json '{"ok": true}'
```

Or from file:

```bash
skiller webhook receive github-ci 42 --json-file payload.json
```

Optional deduplication:

```bash
skiller webhook receive github-ci 42 --json '{"ok": true}' --dedup-key ci-42
```

Command contract: [`commands/webhook.md`](./commands/webhook.md).

## Worker commands

These are operational commands. They are useful for debugging or controlled execution.

Prepare a created run and launch the worker:

```bash
skiller worker start <run_id>
```

Execute a prepared run directly:

```bash
skiller worker run <run_id>
```

Resume a waiting run directly:

```bash
skiller worker resume <run_id>
```

In normal usage, `skiller run` already starts the worker, so most users should not need these commands.

## Command Notes

### `run`

Options:

```bash
skiller run <flow> [--arg key=value] [--logs] [--start-server]
skiller run --file <path> [--arg key=value] [--logs] [--start-server]
```

Notes:
- use `<flow>` for internal catalog ids
- internal agents resolve from `packages/skiller/agents/<id>/agent.yaml`
- use `--file` for external YAML files
- `--logs` includes current logs in the JSON response
- `--start-server` starts the local webhook server before dispatching the run

### `server`

Operational commands for the local webhook server:

```bash
skiller server start
skiller server status
skiller server stop
```

Notes:
- the managed server state is stored under `~/.skiller/webhooks/managed-<port>.json`
- if `SKILLER_DEBUG_HOME` is set, that directory is used as the effective `HOME`
- `server start` reports whether the running server is managed by Skiller or just already reachable on the local endpoint

Detailed guide:
- [`commands/server.md`](./commands/server.md)
- [`tool-server.md`](tool-server.md)

### `cloudflared`

Operational commands for the Cloudflare tunnel workflow:

```bash
skiller cloudflared login start
skiller cloudflared login status
skiller cloudflared login stop
skiller cloudflared ensure --domain <domain>
skiller cloudflared start
skiller cloudflared status
skiller cloudflared stop
```

Use cases:
- authenticate `cloudflared` in the effective `HOME`
- ensure the remote tunnel, DNS route, and local tunnel config exist
- manage the local connector process with explicit Skiller ownership state

Detailed guide:
- [`tool-cloudflared.md`](tool-cloudflared.md)

### `status`

Command contract: [`commands/status.md`](./commands/status.md).

Returns the current run snapshot, including waiting metadata when present.

Examples:

```bash
skiller status <run_id>
skiller status <run_id> --context
```

Useful fields:
- `status`
- `current`
- `wait_type`
- `prompt`
- `webhook`
- `key`

### `logs`

Command contract: [`commands/logs.md`](./commands/logs.md).

Returns the raw structured event list for a run.

Examples:

```bash
skiller logs <run_id>
skiller logs <run_id> --after <sequence>
skiller logs <run_id> --after <sequence> --limit 100
```

Best used for:
- debugging
- inspecting runtime event order
- understanding failures or branching decisions

Notes:
- `/logs` is a debug/raw surface, not the user-facing transcript
- it should expose exact event payloads rather than transcript-style formatting
- `--after` returns events with `sequence` greater than the provided cursor
- `--limit` caps the number of returned events

### `delete`

Deletes the run row and every database row structurally tied to the run:

- runtime events
- waits
- external events where `run_id` or `consumed_by_run_id` matches
- external receipts whose `dedup_key` belongs to those external events
- persisted execution output bodies

Examples:

```bash
skiller delete <run_id>
```

### `input receive`

Used only for runs blocked on `wait_input`.

Examples:

```bash
skiller input receive <run_id> --text "retry in 5 minutes"
```

### `webhook receive`

Used only for runs blocked on `wait_webhook`.

Examples:

```bash
skiller webhook receive github-ci build-42 --json '{"status": "ok"}'
```

## Recommended Usage

### User flow

```bash
skiller run ant
skiller status <run_id>
skiller input receive <run_id> --text "hola"
skiller status <run_id>
```

### Debug flow

```bash
skiller status <run_id>
skiller logs <run_id>
```

### Waiting webhook flow

```bash
skiller run --file ./wait_webhook.yaml --arg key=42
skiller status <run_id>
skiller webhook receive github-ci 42 --json '{"ok": true}'
skiller status <run_id>
```
