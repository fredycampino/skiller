# `assign`

## Goal

`assign` is a pure mapping step. It copies already rendered values into a new named step execution.

## Shape

```yaml
- assign: prepare_issue
  values:
    action: "{{step_executions.analyze_issue.output.value.data.next_action}}"
    summary: "{{step_executions.analyze_issue.output.value.data.summary}}"
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
{{step_executions.prepare_issue.output.value.assigned.action}}
{{step_executions.prepare_issue.output.value.assigned.summary}}
```
