# `notify`

## Goal

`notify` is the simplest operational step in the runtime.

It does not call external services or transform complex data.
It only emits a message, stores its result in the context, and decides whether the run continues or ends.

## Minimal Shape

```yaml
- id: start
  type: notify
  message: "notify smoke ok"
```

## Shape with `next`

```yaml
- id: start
  type: notify
  message: "first"
  next: done

- id: done
  type: notify
  message: "second"
```

## Rendering

`notify` follows the normal runtime pattern:

- `RenderCurrentStepUseCase` renders the full step
- `message` is renderable

Supported placeholders:

- `{{inputs...}}`
- `{{results...}}`

Example:

```yaml
- id: done
  type: notify
  message: "{{results.start.next_action}}"
```

## Result

`notify` stores the result in:

```yaml
results.<step_id>
```

With this shape:

```json
{
  "ok": true,
  "message": "retry"
}
```

## Persistence

In addition to the result in `context.results[step_id]`, `notify` emits:

```text
NOTIFY
```

with:

- `step`
- `message`

## Transition

In the new loop:

- if the step has `next`, the runtime moves `current` to that `step_id`
- if the step has no `next`, the run completes

## Restrictions

In this version:

- `message` is treated as a string
- `next`, if present, must be a non-empty `step_id`
