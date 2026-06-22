# Flow File Schema

## Status

Pending design.

This document describes the YAML flow shape used by:
- internal catalog entries shipped with Skiller under `packages/skiller/agents/<id>/agent.yaml`
- external files passed through `skiller run --file ...`

## Root Shape

```yaml
name: demo_chat
description: "Terminal agent chat"
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
- `on_success`
- `on_error`

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
- `step_id` must be unique within the file

Supported `step_type` values:
- `agent`
- `assign`
- `send`
- `notify`
- `shell`
- `mcp`
- `switch`
- `when`
- `wait_channel`
- `wait_input`
- `wait_webhook`

## Example

```yaml
name: demo_chat
description: "Terminal agent chat"
version: "0.1"
start: ask_user

inputs:
  topic: string

steps:
  - wait_input: ask_user
    prompt: "Write a message about {{inputs.topic}}. Type exit, quit, or bye to stop."
    next: decide_exit

  - switch: decide_exit
    value: '{{output_value("ask_user").payload.text}}'
    cases:
      exit: done
      quit: done
      bye: done
    default: answer

  - agent: answer
    task: '{{output_value("ask_user").payload.text}}'
    next: ask_user

  - notify: done
    message: "Chat closed."
```

## Runtime Access

Templates in flow definitions may read runtime values such as root inputs,
previous step outputs, and the current flow directory.

See [`flow-context.md`](flow-context.md) for the supported namespaces, output
value shapes, and template access rules.

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

## Root End Actions

`on_success` and `on_error` may define a run or post action to expose after the run
finishes. They may also request cleanup after the terminal event is written.

```yaml
on_error:
  cleanup: true
  action:
    type: run
    label: "Debug failure"
    arg: "--file ./flows/debug.yaml"
    params: "--run {{inputs.run_id}}"
    auto: true
```

Post action:

```yaml
on_success:
  action:
    type: post
    label: "Continue"
    arg: "auth-session"
    params: "--provider bedrock"
    auto: true
```

Rules:
- `cleanup` is optional and must be boolean
- `action` is optional when `cleanup: true` is present
- when `action` is present, `action.type` must be `run` or `post`
- when `action` is present, `action.label` is required
- when `action` is present, `action.arg` is required
- when `action` is present, `action.params` is optional
- when `action` is present, `action.auto` is optional and defaults to `false`

## `shell` Example

```yaml
steps:
  - shell: run_tests
    command: ./.venv/bin/pytest packages/skiller/tests/unit -q
    cwd: .
    env:
      FOO: bar
    timeout: 60
    check: true
    next: done
```

## `agent` Example

```yaml
steps:
  - agent: ci_agent
    system:
      file: "./system.md"
    task: '{{output_value("ask_user").payload.text}}'
    tools:
      - shell
    max_turns: 30
    next: ask_user
```

`system.file` is resolved relative to the selected YAML file directory. Absolute
paths and paths escaping that directory are rejected.

## Validation Rules

### Flow

- `start` must exist.
- `steps` must not be empty.
- `start` must reference an existing `step_id`.

### Steps

- each step must define exactly one primary header
- the primary header must use a known `step_type`
- the primary header value must be a non-empty string
- `step_id` values must be unique
