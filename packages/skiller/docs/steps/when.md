# `when`

## Goal

`when` routes execution by evaluating ordered branches over one rendered value.

## Shape

```yaml
- when: decide_score
  value: "{{inputs.score}}"
  branches:
    - gt: 90
      then: excellent
    - gt: 70
      then: good
  default: fail
```

Supported operators:
- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`

## Persistence

```json
{
  "output": {
    "text": "Route selected: good.",
    "value": {
      "next_step_id": "good"
    },
    "body_ref": null
  }
}
```

The decision details are kept in `evaluation.matched_branch`, `evaluation.operator`, and `evaluation.right`.
