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

The runtime automatically allows only the active Python executable path
(`{{runtime.python}}`). It does not automatically allow the runtime working
directory, the flow directory, or the whole Python environment. This path
exception does not add Python to `allowed_commands`; with the allowlist enabled,
its executable name must still be explicitly allowed.

Configured paths are added to the executable path, and duplicates are removed.

The command policy validates paths visible in the outer command. This includes
literal paths and the supported environment expansions `$VAR`,
`${VAR}`, `~`, and `~/path`. The expanded path must
still be inside an allowed root. Expansions `~+`, `~-`, and
`~user` are not supported. Heredoc bodies are accepted only when the delimiter is
quoted or escaped, such as `<<'EOF'`, `<<"EOF"`, or `<<\EOF`; unquoted
heredocs are rejected because Bash may execute substitutions in their bodies.

This validation is not an operating-system sandbox. It does not inspect or
restrict filesystem access performed internally by an allowed executable,
script, or nested interpreter. Granting commands such as `sh`, `bash`, or
`python` through `allowed_commands` delegates that behavior to those programs.
Use an operating-system sandbox when access must be enforced for the complete
process tree.

`allowed_paths` accepts absolute paths, `~`, paths relative to the flow directory, and these exact templates:

- `{{flow.dir}}`: directory containing the current flow YAML;
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

Path entries accept absolute paths, `~`, paths relative to the flow directory, and these exact templates:

- `{{flow.dir}}`: directory containing the current flow YAML;
- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.venv}}`: active Python environment root.

Any other template is invalid. Files grants no paths by default; when no roots
are configured, files actions are blocked.

## Path Resolution

Tool path entries are expanded and resolved when `agent.json` is loaded.
Relative entries resolve against the directory containing the current flow YAML.
`.` and `{{flow.dir}}` identify the same directory, whether `tools` comes from
the global config, a local config, or an external profile. A config that defines
`tools` replaces the whole global `tools` section, without changing this base.

Templates do not grant permissions by themselves: paths must appear explicitly
in the corresponding tool permission lists, except for shell's Python executable
exception described above.

Tool call paths have execution semantics, distinct from configuration entries:

- `files.path` relative paths resolve against the current runtime working directory.
- Missing or blank `shell.cwd` uses the runtime working directory; relative `cwd`
  resolves against that directory, independently of the order of `allowed_paths`.
- The resolved shell working directory must be explicitly allowed and must exist.
  An empty permission list never falls back to allowing the working directory.
- Shell command paths resolve against the effective command working directory.

These rules describe agent tools, not the separate YAML `shell` step policy.

## Validation

Unknown tool config keys fail config mapping. There are no tool environment
overrides in the current mapper.
