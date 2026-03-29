# CLI Command Guide

This guide documents the current `skiller` CLI commands and how they fit into the runtime flow.

Terminology used in this guide:
- transcript = the user-facing execution view rendered by the TUI
- `/logs` = the raw debug event stream

## Command Overview

### Run lifecycle

```bash
skiller run <skill>
skiller run --file <skill.yaml>
skiller resume <run_id>
```

### Inspection

```bash
skiller status <run_id>
skiller runs [--limit N] [--status WAITING] [--status FAILED]
skiller logs <run_id>
skiller watch <run_id>
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

### Setup

```bash
skiller init-db
```

## Typical Flows

## Run a skill

Internal skill:

```bash
skiller run notify_test
```

External file:

```bash
skiller run --file skills/chat.yaml
```

With inputs:

```bash
skiller run story_router --arg path=cave --arg mood=curious
```

What it does:
- creates a run
- snapshots the skill into the database
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

Raw event log:

```bash
skiller logs <run_id>
```

Live progress until the run stabilizes:

```bash
skiller watch <run_id>
```

`watch`:
- polls `status`
- reads new events from `logs`
- prints progress to `stderr`
- returns final JSON to `stdout`
- stops on `WAITING`, `SUCCEEDED`, `FAILED`, or `CANCELLED`

Rule of thumb:
- use `watch` to follow a run as it evolves
- use `logs` when you need the raw event payloads

## Resume a waiting run with text

```bash
skiller input receive <run_id> --text "database timeout"
```

What it does:
- persists the input event
- matches it against the waiting run
- marks the run resumable

If needed, you can resume explicitly:

```bash
skiller resume <run_id>
```

Typical inspection flow:

```bash
skiller status <run_id>
skiller input receive <run_id> --text "database timeout"
skiller watch <run_id>
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
skiller run <skill> [--arg key=value] [--logs] [--start-webhooks]
skiller run --file <path> [--arg key=value] [--logs] [--start-webhooks]
```

Notes:
- use `<skill>` for internal skills
- use `--file` for external YAML files
- `--logs` includes current logs in the JSON response
- `--start-webhooks` starts the webhook process before dispatching the run

### `status`

Returns the current run snapshot, including waiting metadata when present.

Examples:

```bash
skiller status <run_id>
```

Useful fields:
- `status`
- `current`
- `wait_type`
- `prompt`
- `webhook`
- `key`

### `logs`

Returns the raw structured event list for a run.

Examples:

```bash
skiller logs <run_id>
```

Best used for:
- debugging
- inspecting runtime event order
- understanding failures or branching decisions

Notes:
- `/logs` is a debug/raw surface, not the user-facing transcript
- it should expose exact event payloads rather than transcript-style formatting

### `watch`

Best used for:
- following a run live
- seeing the execution transcript evolve
- waiting until the run stabilizes

Examples:

```bash
skiller watch <run_id>
```

Notes:
- `watch` returns structured JSON on `stdout`
- `watch` may print compact progress lines to `stderr` for direct CLI usage
- the TUI transcript should render from structured `events`, not from `stderr` text

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
skiller run chat
skiller watch <run_id>
skiller input receive <run_id> --text "hola"
skiller watch <run_id>
```

### Debug flow

```bash
skiller status <run_id>
skiller logs <run_id>
skiller watch <run_id>
```

### Waiting webhook flow

```bash
skiller run --file skills/wait_webhook_test.yaml --arg key=42
skiller status <run_id>
skiller webhook receive github-ci 42 --json '{"ok": true}'
skiller watch <run_id>
```
