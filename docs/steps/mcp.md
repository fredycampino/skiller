# `mcp`

## Goal

`mcp` runs a tool from an MCP server declared in the skill.

The step:

- renders its arguments with the run context
- resolves the MCP server configuration from the `mcp:` block
- runs the tool
- stores the result in `results.<step_id>`
- decides whether the run continues or ends

## Minimal Shape

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py

steps:
  - id: start
    type: mcp
    mcp: local-mcp
    tool: files_action
    args:
      action: create
      path: "{{inputs.file_path}}"
      content: "{{inputs.content}}"
```

## Shape with `next`

```yaml
mcp:
  - name: test-mcp
    transport: streamable-http
    url: "{{inputs.mcp_url}}"

steps:
  - id: start
    type: mcp
    mcp: test-mcp
    tool: ping
    args: {}
    next: done

  - id: done
    type: notify
    message: "pong"
```

## Rendering

`mcp` follows the normal runtime pattern:

- `RenderCurrentStepUseCase` renders the full step
- `RenderMcpConfigUseCase` renders the MCP configuration declared in the skill

Common renderable fields:

- `args`
- `mcp[].url`
- `mcp[].command`
- `mcp[].args`
- `mcp[].cwd`
- `mcp[].env`
- `mcp[].headers`

## Validations

In this version:

- the step must declare `mcp`
- the step must declare `tool`
- `tool` must not use an `mcp.<server>.` prefix
- `args` must be an object
- the server must exist in the `mcp:` block
- the rendered MCP configuration must not leave templates unresolved

## Result

`mcp` stores the tool result in:

```yaml
results.<step_id>
```

Example:

```json
{
  "ok": true,
  "path": "/tmp/demo.txt"
}
```

## Persistence

In addition to the result in `context.results[step_id]`, `mcp` emits:

```text
MCP_RESULT
```

with:

- `step`
- `mcp`
- `tool`
- `result`

## Transition

In the new loop:

- if the step has `next`, the runtime moves `current` to that `step_id`
- if the step has no `next`, the run completes
