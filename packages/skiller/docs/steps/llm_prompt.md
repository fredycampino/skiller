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
    {{output_value("test_run").data.stderr}}
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

Template access:

```text
{{step_executions.analyze_issue.output.text}}
{{output_value("analyze_issue").data.summary}}
{{output_value("analyze_issue").data.next_action}}
```

The selected model is stored in `evaluation.model`.

Notes:
- `text_ref` tells the UI how to rebuild the full human text from the persisted body.
- templates should read the canonical value through `output_value("analyze_issue")`.
