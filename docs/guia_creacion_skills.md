# Skill Creation Guide

## Goal

Define the canonical YAML format for a skill and the minimum rules required for the current runtime to execute it.

## Current Runtime

At this stage of the refactor, the canonical loop already supports:

- `assign`
- `notify`
- `llm_prompt`
- `mcp`
- `wait_webhook`

Other `type` values may still exist in the repo, but they are outside the current canonical execution path.

## Location and Format

- Folder: `skills/`
- Recommended extension: `.yaml`
- `name` must match the file name

## Loading Skills

There are two ways to execute a skill:

- `internal`: by name from `skills/`
- `file`: by explicit `.yaml` or `.json` path

Examples:

```bash
skiller run notify_test
skiller run --file /path/to/my_skill.yaml
```

When a run is created, the skill is frozen as a snapshot inside the DB.
If the YAML changes later, it only affects new runs.

## Current Flow Rules

- the initial step must have `id: start`
- `GetStartStepUseCase` sets `run.current` to `start`
- in the migrated path, each step decides the next transition
- for `notify`, `assign`, `llm_prompt`, `mcp`, and `wait_webhook`, `next` is optional
- if one of those steps has no `next`, the run completes when that step resolves

## Examples

### Skill with `assign`

```yaml
name: assign_demo
description: "Minimal assign test"
version: "0.1"

inputs:
  issue: string

steps:
  - id: start
    type: assign
    values:
      action: retry
      summary: "{{inputs.issue}}"
    next: done

  - id: done
    type: notify
    message: "{{results.start.action}}"
```

### Skill with `llm_prompt`

```yaml
name: llm_prompt_test
description: "Minimal llm_prompt test"
version: "0.1"

inputs:
  issue: string

steps:
  - id: start
    type: llm_prompt
    prompt: |
      Analyze this issue:
      {{inputs.issue}}
    next: done
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
            enum: [low, medium, high]
          next_action:
            type: string
            enum: [retry, ask_human, fail]

  - id: done
    type: notify
    message: "{{results.start.next_action}}"
```

### Skill with `notify`

```yaml
name: notify_test
description: "Minimal single-step notify test"
version: "0.1"

inputs: {}

steps:
  - id: start
    type: notify
    message: "notify smoke ok"
```

### Skill with `notify` and `next`

```yaml
name: notify_chain
description: "Two chained notify steps"
version: "0.1"

inputs: {}

steps:
  - id: start
    type: notify
    message: "first"
    next: done

  - id: done
    type: notify
    message: "second"
```

### Skill with `mcp`

```yaml
name: stdio_mcp_test
description: "Minimal MCP test over stdio"
version: "0.1"

inputs:
  file_path: string
  content: string

mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py
    cwd: /opt/local-mcp

steps:
  - id: start
    type: mcp
    mcp: local-mcp
    tool: files_action
    args:
      action: create
      path: "{{inputs.file_path}}"
      content: "{{inputs.content}}"
    next: done

  - id: done
    type: notify
    message: "created"
```

### Skill with `wait_webhook`

```yaml
name: wait_webhook_test
description: "Minimal wait_webhook test"
version: "0.1"

inputs:
  key: string

steps:
  - id: start
    type: wait_webhook
    webhook: test
    key: "{{inputs.key}}"
    next: done

  - id: done
    type: notify
    message: "resumed from webhook"
```

## Rules for the `mcp` Block

Each MCP server declared under `mcp:` must define:

- `name`
- `transport`

Depending on `transport`:

- `stdio` requires `command`
- `http` or `streamable-http` requires `url`

Optional fields:

- `args`
- `cwd`
- `env`
- `headers`

## Rendering

The MCP configuration is rendered with the run context.
Supported templates include `{{inputs.*}}`, `{{results.*}}`, and `{{env.*}}`.

Valid example:

```yaml
mcp:
  - name: github
    transport: streamable-http
    url: "{{env.AGENT_GITHUB_MCP_URL}}"
    headers:
      Authorization: "Bearer {{env.AGENT_GITHUB_MCP_TOKEN}}"
```

If a template stays unresolved, the MCP configuration is invalid.

If the MCP server exposes filesystem tools, do not assume its roots can be controlled from `mcp.env`.
For `local_mcp.py`, `FILES_ALLOWED_ROOTS` belongs to the server configuration and may ignore client-side overrides.

## Common Invalid Cases

### `mcp` step with an undeclared server

```yaml
steps:
  - id: start
    type: mcp
    mcp: local-mcp
    tool: files_action
    args: {}
```

Reason: the step uses `local-mcp`, but `mcp:` does not declare it.

### `stdio` without `command`

```yaml
mcp:
  - name: local-mcp
    transport: stdio
```

### `streamable-http` without `url`

```yaml
mcp:
  - name: github
    transport: streamable-http
```

### Unresolved template

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: "{{inputs.python_bin}}"
```

Reason: if `inputs.python_bin` does not exist, the MCP config is invalid.

### `wait_webhook` without `webhook`

```yaml
- id: start
  type: wait_webhook
  key: "{{inputs.key}}"
```

### `wait_webhook` without `key`

```yaml
- id: start
  type: wait_webhook
  webhook: github-pr-merged
```

### `assign` without `values`

```yaml
- id: start
  type: assign
```

### `assign` with empty `values`

```yaml
- id: start
  type: assign
  values: {}
```

Reason: `assign` requires a non-empty `values` object.

## Minimal Checklist

1. The file lives in `skills/` or is loaded via `--file`.
2. `name` matches the file name.
3. A `steps:` section exists.
4. Each step uses a currently supported runtime `type`: `assign`, `notify`, `llm_prompt`, `mcp`, or `wait_webhook`.
5. If a step uses `type: mcp`, the server exists in `mcp:`.
6. The initial step has `id: start`.
7. The `mcp:` block declares `transport` and the required fields for that transport.
