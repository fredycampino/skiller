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

  - name: github
    transport: streamable-http
    url_file: "~/.skiller/secrets/github_mcp_url"
    headers:
      Authorization:
        file: "~/.skiller/secrets/github_mcp_token"
        prefix: "Bearer "

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
{{output_value("create_file").data.path}}
```

Use `output_value(...)` instead of reading `step_executions.<step_id>.output.value...` directly.

The transport outcome is also kept in `evaluation.ok`.

## Secret Inputs For MCP Config

For HTTP MCP servers you can resolve sensitive values without `.env` templates:

- `url`: inline URL
- `url_env`: environment variable name that contains the URL
- `url_file`: file path that contains the URL
- `headers.<name>` can be:
  - string
  - object with `value` or `env` or `file`, plus optional `prefix`/`suffix`
