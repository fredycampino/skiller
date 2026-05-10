# `assign`

## Goal

`assign` is a pure mapping step. It copies already rendered values into a new named step execution.

## Shape

```yaml
- assign: prepare_issue
  values:
    action: '{{output_value("analyze_issue").data.next_action}}'
    summary: '{{output_value("analyze_issue").data.summary}}'
```

## Persistence

`assign` stores:

```json
{
  "step_executions": {
    "prepare_issue": {
      "step_type": "assign",
      "input": {
        "values": {
          "action": "retry",
          "summary": "dependency timeout"
        }
      },
      "evaluation": {},
      "output": {
        "text": "Values assigned.",
        "value": {
          "assigned": {
            "action": "retry",
            "summary": "dependency timeout"
          }
        },
        "body_ref": null
      }
    }
  }
}
```

Template access:

```text
{{output_value("prepare_issue").assigned.action}}
{{output_value("prepare_issue").assigned.summary}}
```
