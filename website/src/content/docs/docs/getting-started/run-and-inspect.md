---
title: Run and inspect
description: Start a workflow and inspect its persisted status and events.
---

Start an external YAML workflow with:

```bash
skiller run --file ./flow.yaml
```

The JSON response contains a `run_id` and the observed status. Keep the id for later operations.

## Read the current state

```bash
skiller status <run_id>
```

Use status to answer where the run is now: running, waiting, succeeded, or failed.

## Read the event history

```bash
skiller logs <run_id>
```

Logs return ordered runtime events and their payloads. Use them to understand transitions, outputs, tool activity, and failures.

## List recent runs

```bash
skiller runs
skiller runs --status WAITING
```

## Waiting runs

A run can return in `WAITING` without failing. Deliver the matching input or external event to resume it. The [Interactive flow](/docs/demos/interactive-flow/) demonstrates the complete input cycle.
