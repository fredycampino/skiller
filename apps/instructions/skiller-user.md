# CLI Quick Guide

This guide shows common `skiller` CLI workflows. Command contracts live in the
dedicated command documents, and command status is listed in
`<path-docs>/cli/catalogue.md`.

## Start a Run

Open STUI and start a packaged, local, or configured flow:

```bash
skiller @flows
skiller @pr --arg owner=my-org --arg repo=my-repo --arg head=feature/demo --arg base=main
```

On first use, when the runtime database does not exist, STUI ignores the initial reference and runs the existing `auth → info → flows` onboarding sequence.

Start without waiting for the run to finish or reach a wait state:

```bash
skiller run ./my-flow.yaml --detach
```
Start a run without blocking:

```bash
skiller run ~/flows/my-flow.yaml --detach
skiller run ./my-flow.yaml --detach
```

Use a packaged, local, or configured flow reference:

```bash
skiller run @flows
skiller run @reportes/diario
```

Pass root inputs with repeated arguments:

```bash
skiller run @pr --arg owner=my-org --arg repo=my-repo --arg head=feature/demo --arg base=main
```

Command contract: `<path-docs>/cli/commands/run.md`.

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
- `<path-docs>/cli/commands/status.md`
- `<path-docs>/cli/commands/runs.md`
- `<path-docs>/cli/commands/logs.md`


Show the effective runtime configuration:

```bash
skiller config
```


## Continue a Waiting Run

For a run blocked on human input:

```bash
skiller input receive <run_id> --text "database timeout"
```

To remain attached until the resumed run reaches another wait or finishes:

```bash
skiller input receive <run_id> --text "database timeout" --wait
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
- `<path-docs>/cli/commands/input.md`
- `<path-docs>/cli/commands/webhook.md`
- `<path-docs>/cli/commands/channel-exp.md`

## Resume Explicitly

Most ingress commands dispatch worker resume when they match a waiting run. Use
`resume` directly when you need to retry or continue a run manually:

```bash
skiller resume <run_id>
```

Command contract: `<path-docs>/cli/commands/resume.md`.

## Agent Operations

Interrupt the active agent turn without deleting the run:

```bash
skiller agent interrupt <run_id>
```

Inspect context-window statistics:

```bash
skiller agent stats <run_id> --agent <agent_id>
```

Command contract: `<path-docs>/cli/commands/agent.md`.

## Server Operations

Manage the local webhook server process:

```bash
skiller server start
skiller server status
skiller server stop
```

Command contracts:
- `<path-docs>/cli/commands/server.md`
- `<path-docs>/cli/tool-server.md`

## Cleanup

Delete a run and database rows tied to it:

```bash
skiller delete <run_id>
```

Command contract: `<path-docs>/cli/commands/delete.md`.
