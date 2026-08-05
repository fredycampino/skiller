# Agent Tool Configuration

This document describes the `tools` section of `agent.json`.

## Scope

`tools` is optional. `agent.json` can configure only tools that read runtime
configuration. Current configurable tools are:

- `shell`
- `files`

## Shell

`tools.shell` controls what the agent `shell` tool may execute. It restricts the
working directory, explicit path arguments, and optionally the executable names.

```json
{
  "tools": {
    "shell": {
      "allowed_paths": [
        "{{flow.dir}}",
        "{{runtime.venv}}"
      ],
      "allowlist_enabled": false,
      "allow_env_prefix": true,
      "allowed_commands": []
    }
  }
}
```

### `tools.shell.allowed_paths`

Defines the additional filesystem roots where the shell may use `cwd` or
explicit paths in commands.

Effective allowed paths:

- `allowed_paths = ({{runtime.cwd}}, {{runtime.python}},configured paths)`
- `allowlist_enabled = false`
- `allow_env_prefix = true`
- `allowed_commands = ()`

The runtime always includes `{{runtime.cwd}}` and `{{runtime.python}}`. Paths
declared in `agent.json` are added to them. Duplicate paths are kept once.
Relative configured paths are resolved against the directory of `agent.json`.

Shell path:

- `"."`: directory containing `agent.json`.
- `{{flow.dir}}`: directory containing the current flow.
- `{{runtime.venv}}`: root directory of the active Python virtual environment.

### `tools.shell.allowlist_enabled`

When `true`, every executable used by the command must appear in
`tools.shell.allowed_commands`.

### `tools.shell.allow_env_prefix`

When `true`, commands may start with environment assignments such as
`MODE=test command`.

### `tools.shell.allowed_commands`

List of executable names permitted when `allowlist_enabled` is `true`.

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

When no files roots are configured, files actions are blocked.

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
