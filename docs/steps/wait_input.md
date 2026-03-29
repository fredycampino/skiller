# `wait_input`

## Goal

`wait_input` pauses a run until human input is received for the current `run_id + step_id`.

## Shape

```yaml
- wait_input: ask_user
  prompt: "Write a short summary"
  next: done
```

## Waiting Output

When no input has been received yet:

```json
{
  "output": {
    "text": "Write a short summary",
    "value": {
      "prompt": "Write a short summary",
      "payload": null
    },
    "body_ref": null
  }
}
```

`RUN_WAITING` exposes that same `output`.

## Resolved Output

After input is consumed:

```json
{
  "output": {
    "text": "Input received.",
    "value": {
      "prompt": "Write a short summary",
      "payload": {
        "text": "database timeout"
      }
    },
    "body_ref": null
  }
}
```

Template access:

```text
{{step_executions.ask_user.output.value.payload.text}}
```

The consumed external event id is stored in `evaluation.input_event_id`.
