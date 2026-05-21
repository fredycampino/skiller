# Context Model

This document defines the persisted runtime model used by `RunContext`.

## Top Level

```python
RunContext(
    inputs: dict[str, Any],
    step_executions: dict[str, StepExecution],
    steering_queue: list[SteeringItem] = [],
    cancel_reason: str | None = None,
)
```

`SteeringItem`:

```python
SteeringItem =
    SteeringAgentInterrupt
    | SteeringStepInterrupt
    | SteeringAgentMessage
```

Persisted steering items:

```json
{ "type": "agent_interrupt" }
{ "type": "step_interrupt" }
{ "type": "agent_message", "text": "be concise" }
```

Legacy `{target, action}` steering objects can still be read and normalized by
the runtime, but new writes use the `type` shape above.

When `agent_interrupt` is consumed during a running agent tool turn, the runtime
also appends one control `user_message` to the agent context:

```text
[Skiller] User interrupted the current tool turn.
```

That control message belongs to `agent context`, not to `RunContext.step_executions`.

The `agent` step itself still finishes as a normal step result.
If the agent should wait for the user after that, the following explicit wait step is what
creates `RunStatus.WAITING` and `RUN_WAITING`.

In `RunContext.step_executions`, the `agent` step is persisted exactly like any other
step: a normal `StepExecution` with `input`, `evaluation`, and `output`. Its internal
turn transcript stays in `agent context`; its consolidated step result stays in runtime context.

`RunContext` is not an event log. Historical execution order, repeated executions,
and transcript observability are stored in `log_events`.

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
      "step_type": "agent",
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

`step_executions` is keyed by `step_id`. If the same step id executes more than
once, the latest `StepExecution` replaces the previous one.

## Output Model

In memory, the runtime uses typed outputs:

- `AssignOutput`
- `AgentOutput`
- `NotifyOutput`
- `ShellOutput`
- `SwitchOutput`
- `WhenOutput`
- `WaitInputOutput`
- `WaitWebhookOutput`
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
- step outputs are stored inline in `output.value`.

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
    "message": "message body",
    "format": "simple"
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

### `agent`

```json
{
  "text": "Final answer.",
  "text_ref": "data.final.text",
  "value": {
    "data": {
      "context_id": "default",
      "final": {
        "text": "Final answer."
      },
      "turn_count": 2,
      "tool_call_count": 1,
      "stop_reason": "final"
    }
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

### `wait_channel`

```json
{
  "text": "Channel message received: whatsapp:172584771580071@lid.",
  "value": {
    "channel": "whatsapp",
    "key": "172584771580071@lid",
    "payload": {
      "channel": "whatsapp",
      "message_id": "msg-1",
      "key": "172584771580071@lid",
      "sender_id": "172584771580071@lid",
      "sender_name": "Fede",
      "text": "hola",
      "timestamp": 1775388655
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
- direct template access to `step_executions.<step_id>.output.value...` is not allowed.
