# Skill Schema

## Status

Pending design.

This document describes the target YAML shape for skills.

## Root Shape

```yaml
name: chat
description: "Simple chat loop"
version: "0.1"
start: ask_user
steps: [...]
```

Rules:
- `name` is required.
- `start` is required.
- `steps` is required and must be non-empty.
- `start` must point to an existing `step_id`.

Optional root blocks:
- `description`
- `version`
- `inputs`
- `mcp`

## Root `inputs`

```yaml
inputs:
  issue: string
  severity: string
```

Runtime access:

```text
{{inputs.issue}}
{{inputs.severity}}
```

## Step Shape

Each item in `steps` has exactly one primary header:

```yaml
- <step_type>: <step_id>
```

Example:

```yaml
- wait_input: ask_user
  prompt: "Write a message"
  next: decide_exit
```

Rules:
- the primary key is the `step_type`
- the primary value is the `step_id`
- `step_id` must be unique within the skill

Supported `step_type` values:
- `assign`
- `notify`
- `shell`
- `llm_prompt`
- `mcp`
- `switch`
- `when`
- `wait_input`
- `wait_webhook`

## Example

```yaml
name: chat
description: "Simple chat loop"
version: "0.1"
start: ask_user

inputs:
  topic: string

steps:
  - wait_input: ask_user
    prompt: "Write a message about {{inputs.topic}}. Type exit, quit, or bye to stop."
    next: decide_exit

  - switch: decide_exit
    value: "{{step_executions.ask_user.output.value.payload.text}}"
    cases:
      exit: done
      quit: done
      bye: done
    default: answer

  - llm_prompt: answer
    prompt: "{{step_executions.ask_user.output.value.payload.text}}"
    output:
      format: json
      schema:
        type: object
        required: [reply]
        properties:
          reply:
            type: string
    large_result: true
    next: ask_user

  - notify: done
    message: "Chat closed."
```

## Runtime Access

Templates may read:

```text
{{inputs.<name>}}
{{step_executions.<step_id>.output.text}}
{{step_executions.<step_id>.output.value}}
{{step_executions.<step_id>.evaluation}}
```

## Root `mcp`

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py
    cwd: /opt/local-mcp
```

## `shell` Example

```yaml
steps:
  - shell: run_tests
    command: ./.venv/bin/pytest tests/unit -q
    cwd: .
    env:
      FOO: bar
    timeout: 60
    check: true
    large_result: true
    next: done
```

## Validation Rules

### Skill

- `start` must exist.
- `steps` must not be empty.
- `start` must reference an existing `step_id`.

### Steps

- each step must define exactly one primary header
- the primary header must use a known `step_type`
- the primary header value must be a non-empty string
- `step_id` values must be unique
