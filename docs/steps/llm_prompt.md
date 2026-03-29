# `llm_prompt`

## Goal

`llm_prompt` renders `system` and `prompt`, requires JSON output, validates the response against the declared schema, and stores the parsed value as structured output.

## Shape

```yaml
- llm_prompt: analyze_issue
  system: |
    You are a technical analyst.
    Respond only with valid JSON.
  prompt: |
    Analyze this error:
    {{step_executions.test_run.output.value.data.stderr}}
  output:
    format: json
    schema:
      type: object
      required: [summary, severity, next_action]
      properties:
        summary:
          type: string
        severity:
          type: string
        next_action:
          type: string
  large_result: true  # optional
  next: done
```

## Persistence

```json
{
  "output": {
    "text": "retry build",
    "value": {
      "data": {
        "summary": "dependency timeout",
        "severity": "high",
        "next_action": "retry"
      }
    },
    "body_ref": null
  }
}
```

With `large_result: true`:

```json
{
  "output": {
    "text": "Europa es uno de los continentes más pequeños...",
    "text_ref": "data.reply",
    "value": {
      "data": {
        "reply": "Europa es uno de los continentes más pequeños...",
        "reply_length": 980,
        "truncated": true
      }
    },
    "body_ref": "execution_output:abc123"
  }
}
```

Template access:

```text
{{step_executions.analyze_issue.output.text}}
{{step_executions.analyze_issue.output.value.data.summary}}
{{step_executions.analyze_issue.output.value.data.next_action}}
```

The selected model is stored in `evaluation.model`.

Notes:
- without `large_result`, `output.text` and `output.value.data` contain the full parsed result.
- with `large_result: true`, `output.text` and `output.value` are reduced to a small observable summary.
- the full body is stored behind `output.body_ref`.
- `text_ref` tells the UI how to rebuild the full human text from the persisted body.
