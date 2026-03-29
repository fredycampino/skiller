# `switch`

## Goal

`switch` routes execution by exact equality over one rendered value.

## Shape

```yaml
- switch: decide_action
  value: "{{step_executions.prepare_action.output.value.assigned.action}}"
  cases:
    retry: retry_notice
    ask_human: human_notice
    done: done_notice
  default: unknown_action
```

## Persistence

```json
{
  "output": {
    "text": "Route selected: retry_notice.",
    "value": {
      "next_step_id": "retry_notice"
    },
    "body_ref": null
  }
}
```

The selected route is also stored in `evaluation.next_step_id`.
