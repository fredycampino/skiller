# Step `when`

## Goal

`when` routes execution to the next `step_id` by evaluating branches in order over a single value.

## v0 Contract

```yaml
- id: decide_score
  type: when
  value: "{{results.score}}"
  branches:
    - gt: 90
      then: excellent
    - gt: 70
      then: good
  default: fail
```

Fields:

- `value`: required
- `branches`: required, non-empty list
- `default`: required fallback `step_id`

Per-branch rules:

- each branch defines exactly one operator
- each branch defines `then`
- the first matching branch wins

v0 operators:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`

## Semantics

- evaluates `value`
- iterates through `branches` in order
- the first matching branch moves `run.current` to the `step_id` declared in `then`
- if none matches, moves `run.current` to `default`

## Persistence

Stores in `context.results[step_id]`:

```json
{"value": 85, "next": "good"}
```

It also emits:

```json
{"step": "decide_score", "value": 85, "next": "good", "branch": 1, "op": "gt", "right": 70}
```

with type `WHEN_DECISION`.
