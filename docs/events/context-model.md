# Context Model

This document defines the persisted runtime model used by `RunContext`.

## Top Level

```python
RunContext(
    inputs: dict[str, Any],
    step_executions: dict[str, StepExecution],
    steering_messages: list[str] = [],
    cancel_reason: str | None = None,
)
```

Each step stores one `StepExecution`:

```python
StepExecution(
    step_type: StepType,
    input: dict[str, Any],
    evaluation: dict[str, Any],
    output: OutputBase,
)
```

## Persistence Shape

`RunContext.to_dict()` persists:

```json
{
  "inputs": {},
  "step_executions": {
    "<step_id>": {
      "step_type": "llm_prompt",
      "input": {},
      "evaluation": {},
      "output": {
        "text": "hello back",
        "value": {
          "data": {
            "reply": "hello back"
          }
        },
        "body_ref": null
      }
    }
  }
}
```

## Output Model

In memory, the runtime uses typed outputs:

- `AssignOutput`
- `NotifyOutput`
- `ShellOutput`
- `SwitchOutput`
- `WhenOutput`
- `WaitInputOutput`
- `WaitWebhookOutput`
- `LlmPromptOutput`
- `McpOutput`

Publicly, every output is normalized to:

```json
{
  "text": "...",
  "text_ref": "data.reply",
  "value": {},
  "body_ref": null
}
```

Rules:
- `text` is always present.
- `text_ref` is optional and points to the field inside the full body value that can rebuild the full human text.
- `value` is always an object or `null`.
- `body_ref` is always present and may be `null`.
- if `body_ref` is not `null`, `output.value` is the small persisted summary and the full output body is stored separately.

## Per-Step Output Fields

### `assign`

```json
{
  "text": "Values assigned.",
  "value": {
    "assigned": {}
  },
  "body_ref": null
}
```

### `notify`

```json
{
  "text": "message body",
  "value": {
    "message": "message body"
  },
  "body_ref": null
}
```

### `shell`

```json
{
  "text": "hello",
  "value": {
    "ok": true,
    "exit_code": 0,
    "stdout": "hello\n",
    "stderr": ""
  },
  "body_ref": null
}
```

### `switch`

```json
{
  "text": "Route selected: answer.",
  "value": {
    "next_step_id": "answer"
  },
  "body_ref": null
}
```

### `when`

```json
{
  "text": "Route selected: good.",
  "value": {
    "next_step_id": "good"
  },
  "body_ref": null
}
```

### `wait_input`

```json
{
  "text": "Input received.",
  "value": {
    "prompt": "Write a short summary",
    "payload": {
      "text": "database timeout"
    }
  },
  "body_ref": null
}
```

### `wait_webhook`

```json
{
  "text": "Webhook received: github-pr-merged:42.",
  "value": {
    "webhook": "github-pr-merged",
    "key": "42",
    "payload": {
      "merged": true
    }
  },
  "body_ref": null
}
```

### `llm_prompt`

Normal:

```json
{
  "text": "hello back",
  "value": {
    "data": {
      "reply": "hello back"
    }
  },
  "body_ref": null
}
```

With `large_result: true`:

```json
{
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
```

### `mcp`

```json
{
  "text": "local-mcp.files_action completed successfully.",
  "value": {
    "data": {
      "ok": true
    }
  },
  "body_ref": null
}
```

## Template Access

Templates read step data through two channels:

Examples:

```text
{{output_value("ask_user").payload.text}}
{{output_value("answer").data.reply}}
{{output_value("decide_exit").next_step_id}}
{{step_executions.answer.output.text}}
```

Notes:
- `step_executions` stores the persisted output envelope.
- `step_executions.<step_id>.output.text` and `step_executions.<step_id>.evaluation` remain directly readable.
- `output_value("<step_id>")` returns the canonical `output.value` for that step.
- if `output.body_ref` is present, `output_value(...)` resolves the persisted body lazily from `execution_outputs`.
- direct template access to `step_executions.<step_id>.output.value...` is not allowed.
- direct template access to `output.body_ref` is not allowed.
