# Flow Runtime Context

Flow templates may read runtime values from these namespaces.

Use this document when writing YAML templates. For the persisted database tables,
see [`../db/schema.md`](../db/schema.md).

## Inputs

Use `inputs.<name>` to read a root input passed when the run is created.

Pass input values when creating the run with `--arg key=value`.

```bash
skiller run demo_chat --arg topic=databases
```

```yaml
inputs:
  topic: string

steps:
  - wait_input: ask_user
    prompt: "Write a message about {{inputs.topic}}."
```

## Output Values

Use `output_value("<step_id>")` to read the canonical `output.value` stored by a
previous step. Field access can follow the helper.

```yaml
steps:
  - wait_input: ask_user
    prompt: "Write a task"
    next: answer

  - agent: answer
    system: "You are concise."
    task: '{{output_value("ask_user").payload.text}}'
```

Examples:

```text
{{output_value("ask_user").payload.text}}
{{output_value("answer").data.reply}}
{{output_value("decide_exit").next_step_id}}
```

Prefer `output_value("<step_id>")` over direct access to
`step_executions.<step_id>.output.value...`.

## Flow

Use `flow.dir` to read the directory that contains the current flow file.
This is useful for helper files shipped next to a flow.

```yaml
steps:
  - shell: run_helper
    command: python3 "{{flow.dir}}/helper.py"
```

## Step Executions

`step_executions` stores the persisted execution envelope for each completed
step. It is keyed by `step_id`. If the same step id executes more than once,
the latest execution replaces the previous one.

Readable advanced fields:

- `step_executions.<step_id>.output.text`
- `step_executions.<step_id>.output.text_ref`
- `step_executions.<step_id>.output.body_ref`
- `step_executions.<step_id>.evaluation`

Use these fields only when `output_value("<step_id>")` does not cover the needed
data.

```text
{{step_executions.answer.output.text}}
{{step_executions.answer.evaluation.model}}
```

Do not read `step_executions.<step_id>.output.value...` directly. Use
`output_value("<step_id>")` for canonical output values.

## Output Envelope

Each completed step stores one output envelope:

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
- `text_ref` is optional and points to the field inside `value` that can rebuild
  the human text.
- `value` is always an object or `null`.
- `body_ref` is always present and may be `null`.
- step outputs are stored inline in `output.value`.

## Per-Step Output Values

### `assign`

```json
{
  "assigned": {}
}
```

### `notify`

```json
{
  "message": "message body",
  "format": "simple"
}
```

`action` is present only when a notify action is configured.

### `send`

```json
{
  "channel": "external",
  "key": "contact-1",
  "message": "hello",
  "message_id": "msg-1"
}
```

### `shell`

```json
{
  "ok": true,
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": ""
}
```

### `agent`

Final output:

```json
{
  "data": {
    "context_id": "default",
    "final": "Final answer.",
    "turn_count": 2,
    "tool_call_count": 1,
    "stop_reason": "final",
    "usage": {
      "prompt_tokens": 100,
      "completion_tokens": 20,
      "total_tokens": 120,
      "provider": "minimax",
      "model": "MiniMax-M2.5"
    }
  }
}
```

`usage` is present when the selected LLM provider returns token usage.

Stop output:

```json
{
  "data": {
    "context_id": "default",
    "message": "Agent stopped after reaching max turns.",
    "turn_count": 8,
    "tool_call_count": 2,
    "stop_reason": "max_turns_exhausted"
  }
}
```

Config-invalid output:

```json
{
  "data": {
    "context_id": "",
    "message": "Provider 'minimax' does not support model='bad-model'. (PROVIDER_MODEL_UNSUPPORTED)",
    "turn_count": 0,
    "tool_call_count": 0,
    "stop_reason": "config_invalid"
  }
}
```

### `switch`

```json
{
  "next_step_id": "answer"
}
```

### `when`

```json
{
  "next_step_id": "good"
}
```

### `wait_input`

```json
{
  "prompt": "Write a short summary",
  "payload": {
    "text": "database timeout"
  }
}
```

### `wait_channel`

```json
{
  "channel": "external",
  "key": "contact-1",
  "payload": {
    "message_id": "msg-1",
    "key": "contact-1",
    "sender_id": "contact-1",
    "sender_name": "Sender",
    "text": "hello",
    "timestamp": 1775388655
  }
}
```

### `wait_webhook`

```json
{
  "webhook": "github-pr-merged",
  "key": "42",
  "payload": {
    "merged": true
  }
}
```

### `mcp`

```json
{
  "data": {
    "ok": true
  }
}
```
