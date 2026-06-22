# CLI Quick Guide

This guide shows common `skiller` CLI workflows. Command contracts live in the
dedicated command documents, and command status is listed in
[`catalogue.md`](catalogue.md).

## Start a Run

Use an internal flow id:

```bash
skiller run mono
```

Use an external flow file:

```bash
skiller run --file ./my-flow.yaml
```

Pass root inputs with repeated arguments:

```bash
skiller run pr --arg owner=my-org --arg repo=my-repo --arg head=feature/demo --arg base=main
```

Command contract: [`commands/run.md`](commands/run.md).

## Inspect a Run

Read the current run state:

```bash
skiller status <run_id>
```

List recent runs:

```bash
skiller runs
skiller runs --status WAITING
skiller runs --status FAILED --limit 50
```

Read raw runtime events:

```bash
skiller logs <run_id>
```

Use `status` for the current snapshot and `logs` when you need event payloads,
ordering, or failure details.

Command contracts:
- [`commands/status.md`](commands/status.md)
- [`commands/runs.md`](commands/runs.md)
- [`commands/logs.md`](commands/logs.md)

## Continue a Waiting Run

For a run blocked on human input:

```bash
skiller input receive <run_id> --text "database timeout"
```

For a run blocked on a webhook:

```bash
skiller webhook receive github-ci build-42 --json '{"status": "ok"}'
```

For generic channel ingress:

```bash
skiller channel receive alerts build-42 --json '{"text": "done"}'
```

`channel` is experimental. Use `input` and `webhook` for stable public flows.

Command contracts:
- [`commands/input.md`](commands/input.md)
- [`commands/webhook.md`](commands/webhook.md)
- [`commands/channel-exp.md`](commands/channel-exp.md)

## Resume Explicitly

Most ingress commands dispatch worker resume when they match a waiting run. Use
`resume` directly when you need to retry or continue a run manually:

```bash
skiller resume <run_id>
```

Command contract: [`commands/resume.md`](commands/resume.md).

## Agent Operations

Interrupt the active agent turn without deleting the run:

```bash
skiller agent interrupt <run_id>
```

Inspect context-window statistics:

```bash
skiller agent stats <run_id> --agent <agent_id>
```

Command contract: [`commands/agent.md`](commands/agent.md).

## Server Operations

Manage the local webhook server process:

```bash
skiller server start
skiller server status
skiller server stop
```

Command contracts:
- [`commands/server.md`](commands/server.md)
- [`tool-server.md`](tool-server.md)

## Cleanup

Delete a run and database rows tied to it:

```bash
skiller delete <run_id>
```

Command contract: [`commands/delete.md`](commands/delete.md).

## Development Worker Commands

Worker commands are development/operator commands. Normal CLI usage should go
through `run`, `resume`, `input receive`, `webhook receive`, or `channel receive`.

```bash
skiller worker start <run_id>
skiller worker run <run_id>
skiller worker resume <run_id>
```

Command contract: [`commands/worker-dev.md`](commands/worker-dev.md).
