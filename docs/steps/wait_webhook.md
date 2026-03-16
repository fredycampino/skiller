# `wait_webhook`

## Status

Active functional design.

The base step is already implemented, but some details may still change during development, especially if we find:
- duplicate `webhook + key` problems
- new correlation needs
- changes in how the `webhooks` process operates

## Goal

`wait_webhook` pauses a run until an external event arrives.

It should:
- leave the run in `WAITING`
- persist a durable wait
- resume the flow when a webhook with the expected `webhook + key` arrives

## Minimal Shape

```yaml
- id: start
  type: wait_webhook
  webhook: github-pr-merged
  key: "{{results.create_pr.pr}}"
  next: done
```

## Rendering

`wait_webhook` follows the current runtime pattern:

- `RenderCurrentStepUseCase` renders the full step
- `webhook` is renderable
- `key` is renderable

Supported placeholders:
- `{{inputs...}}`
- `{{results...}}`

## Waiting Semantics

When the step runs:

1. if no persisted event exists for that `webhook + key`:
- the run moves to `WAITING`
- an entry in `waits` is created or reused
- `current` stays on the same step
- the step is not consumed yet

2. if the event already exists:
- the step resolves
- the result is written to `context.results[step_id]`
- if `next` exists, the run moves `current` to that step
- if `next` does not exist, the run completes

## Result

When the step resolves, the expected result looks like:

```yaml
results.wait_merge.ok
results.wait_merge.webhook
results.wait_merge.key
results.wait_merge.payload
```

Example:

```json
{
  "ok": true,
  "webhook": "github-pr-merged",
  "key": "42",
  "payload": {
    "merged": true
  }
}
```

## Webhook Reception

The current minimal system entrypoint is:

```text
POST /webhooks/{webhook}/{key}
```

The received event must:
- be persisted first
- and only then attempt to resume the run

## Resume Flow

The expected flow is:

1. the webhook arrives
2. the event is persisted
3. `HandleWebhookUseCase` finds candidate runs
4. `ResumeRunUseCase` makes the run resumable
5. the runtime re-enters the loop
6. `ExecuteWaitWebhookStepUseCase` finds the persisted event and resolves the step

## Expected Use Case

Current name:

- `ExecuteWaitWebhookStepUseCase`

Responsibility:
- execute the `wait_webhook` step
- leave the run in `WAITING` if no event exists
- resolve the same step if the event already exists
- return `NEXT`, `COMPLETED`, or `WAITING` to the loop

## Important Functional Rules

- a waiting step must not be consumed before it resolves
- the waiting step itself must own its own resolution when the event already exists
- the webhook must be persisted before attempting to resume the run
- the waiting state must survive process restarts and machine shutdowns

## Current Direction

The current base uses correlation by:

- `webhook`
- `key`

And it still leaves one important decision open:

- what to do when duplicate `webhook + key` values exist
