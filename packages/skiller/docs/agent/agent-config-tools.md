# Agent Tool Configuration

This document describes the `tools` section of `agent.json`.

## Scope

`tools` is optional. `agent.json` can configure only tools that read runtime
configuration. Current configurable tools are:

- `shell`
- `files`

## Shell

`tools.shell` restricts the working directory, explicit command paths, and
optionally the executable names available to the agent `shell` tool.

```json
{
  "tools": {
    "shell": {
      "allowed_paths": ["{{flow.dir}}", "{{runtime.venv}}"],
      "allowlist_enabled": false,
      "allow_env_prefix": true,
      "allowed_commands": []
    }
  }
}
```

| Field | Default | Purpose |
|---|---|---|
| `allowed_paths` | `[]` | Adds filesystem roots available to `cwd` and explicit command paths. |
| `allowlist_enabled` | `false` | Requires every executable to be listed in `allowed_commands`. |
| `allow_env_prefix` | `true` | Allows commands to start with assignments such as `MODE=test`. |
| `allowed_commands` | `[]` | Lists executable names allowed when the allowlist is enabled. |

### Allowed paths

The runtime always allows:

- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.python}}`: active Python executable.

Do not add these paths unless needed for clarity. Configured paths are added to
the defaults, and duplicates are removed.

`allowed_paths` accepts absolute paths, `~`, paths relative to the `agent.json`
that defines `tools`, and these exact templates:

- `{{flow.dir}}`: directory of that `agent.json`;
- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.python}}`: active Python executable;
- `{{runtime.venv}}`: active Python environment root.

Any other template is invalid.

## Files

`tools.files` controls what the agent `files` tool may read or modify. Read and
write roots are independent, and `all` grants both permissions.

```json
{
  "tools": {
    "files": {
      "read": ["."],
      "write": ["."],
      "all": []
    }
  }
}
```

Fields:

- `tools.files.read`
- `tools.files.write`
- `tools.files.all`

Defaults:

- `read = ()`
- `write = ()`
- `all = ()`

`tools.files.all` grants both read and write access. `tools.files.read` only
grants read access. `tools.files.write` grants write and edit access.

Path entries accept absolute paths, `~`, paths relative to the `agent.json` that
defines `tools`, and these exact templates:

- `{{flow.dir}}`: directory of that `agent.json`;
- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.venv}}`: active Python environment root.

Any other template is invalid. Files grants no paths by default; when no roots
are configured, files actions are blocked.

## Path Resolution

Tool path entries are expanded and resolved when `agent.json` is loaded.
Relative entries are resolved against the directory of the `agent.json` file
that defines the `tools` section.

- global `~/.skiller/settings/agent.json`: `.` is `~/.skiller/settings`
- explicit `AGENT_AGENT_CONFIG_FILE`: `.` is its directory
- local flow `<flow-directory>/agent.json`: `.` is `<flow-directory>`

If a local or explicit config defines `tools`, it replaces the whole global
`tools` section. Replacement paths therefore resolve against the local or
explicit file. Use absolute paths for stable shared global config.

## Validation

Unknown tool config keys fail config mapping. There are no tool environment
overrides in the current mapper.
