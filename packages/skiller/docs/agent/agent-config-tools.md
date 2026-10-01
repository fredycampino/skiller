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

### Restricted command syntax

With `allowlist_enabled: true`, each outer command separated by a newline, `;`,
`|`, `&&`, or `||` is checked. Executables must be literal: quoted literal
concatenation is accepted, but variables, tilde, globbing and other active
expansions in executable names are rejected.

Command/process substitutions, background `&`, `|&`, `&>`, `&>>`, groups,
subshells, functions, control flow, and active reserved prefixes such as `time`,
`!`, and `coproc` are unsupported. Literal mentions inside quotes or quoted
heredoc bodies do not execute commands and are not treated as substitutions.
Heredoc recognition respects comments and continued command lines. Active
Bash dollar-quoted heredoc delimiters (`$'EOF'` and `$"EOF"`), including
concatenated forms, are rejected before excluding any body in both modes.
Backslash escapes inside double-quoted heredoc delimiters are also rejected
before excluding any body. Ordinary delimiters, escapes outside quotes, and
literal backslashes inside single quotes remain supported.

Redirections before the executable are rejected. Supported file redirections
follow the executable; use `>./output 2>&1` instead of `&>./output`.
Descriptor duplication/closing requires a literal descriptor or `-`.

Nonempty tool-call `env` is rejected in this mode: variables such as `BASH_ENV`
can execute startup code before the validated command. The worker environment
and its shell configuration remain trusted. `allow_env_prefix` is a separate,
explicit delegation of the permitted program's environment, not authorization
for tool-call `env`.

With the allowlist disabled, these new syntax and environment restrictions do
not apply; existing path, critical-command and heredoc checks still apply.
This is bounded hardening against known outer-shell bypasses, not a complete
shell security model or a network sandbox. Allowed interpreters and command
launchers still delegate their internal behavior. The syntax targets Bash and
POSIX `/bin/sh`; operators configuring another `$SHELL` must ensure compatible
semantics. The runtime does not change shell selection.

### Allowed paths

The runtime always allows:

- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.python}}`: active Python executable.

Do not add these paths unless needed for clarity. Configured paths are added to
the defaults, and duplicates are removed.

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
