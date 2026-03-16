# Step `switch`

## Goal

`switch` routes execution to the next `step_id` based on exact equality over an already normalized value.

## v0 Contract

```yaml
- id: decide_action
  type: switch
  value: "{{results.start.action}}"
  cases:
    retry: retry_notice
    ask_human: human_notice
    done: done_notice
  default: unknown_action
```

Fields:

- `value`: required
- `cases`: required, non-empty object with shape `value -> step_id`
- `default`: required fallback `step_id`

## Semantics

- evaluates `value`
- compares it by exact equality against the keys in `cases`
- if there is a match, moves `run.current` to the associated `step_id`
- if there is no match, moves `run.current` to `default`

## Persistence

Stores in `context.results[step_id]`:

```json
{"value": "retry", "next": "retry_notice"}
```

It also emits:

```json
{"step": "decide_action", "value": "retry", "next": "retry_notice"}
```

with type `SWITCH_DECISION`.
