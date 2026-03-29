# `mcp`

## Goal

`mcp` runs a tool from an MCP server declared in the skill and stores the returned tool payload as structured output.

## Shape

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py

steps:
  - mcp: create_file
    server: local-mcp
    tool: files_action
    args:
      action: create
      path: "{{inputs.file_path}}"
      content: "{{inputs.content}}"
```

Optional:

```yaml
steps:
  - mcp: search
    server: local-mcp
    tool: search
    args:
      query: "{{inputs.query}}"
    large_result: true
```

## Persistence

```json
{
  "output": {
    "text": "local-mcp.files_action completed successfully.",
    "value": {
      "data": {
        "ok": true,
        "path": "/tmp/demo.txt"
      }
    },
    "body_ref": null
  }
}
```

With `large_result: true`, the runtime stores the full `output_body` in `execution_outputs`, keeps a small summary in `output.value.data`, marks it with `truncated: true`, and fills `output.body_ref`.

Template access:

```text
{{step_executions.create_file.output.value.data.path}}
```

The transport outcome is also kept in `evaluation.ok`.
