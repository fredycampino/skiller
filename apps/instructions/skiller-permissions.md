## Agent configuration and tool permissions

Never bypass permission checks. Read `<path-docs>/agent/agent-config.md` and
`<path-docs>/agent/agent-config-tools.md` for the complete contracts.

### Select the profile explicitly

For new or updated flows, declare `config.file` on the `agent` step:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
  system: "Review the requested changes."
  task: "{{inputs.task}}"
```

The profile can have any filename. `config.file` accepts absolute paths, `~`,
relative paths, `$PROFILE_FILE`, and concatenations such as
`${PROFILE_DIR}/reviewer.json`. Relative paths start at the directory containing
the flow YAML. Variables come from the Runtime process environment, must exist
and be non-empty, and are expanded once. Do not use `{{...}}` templates in this
field. An explicit missing or invalid profile is an error, not a fallback.

The selected profile overrides the global `~/.skiller/settings/agent.json` by
root section, without recursive merging. An explicit profile replaces the
conventional local profile; the two are not combined. When `config.file` is
omitted, the Runtime still uses `agent.json` beside the YAML if present, otherwise
only the global file. This implicit local discovery is planned for deprecation;
prefer explicit `config.file`. The global configuration remains supported.

### Configuration paths and templates

Relative paths inside `tools` always start at the directory containing the flow
YAML, even when the profile is external or the tools come from global settings.
`./` and `{{flow.dir}}` denote that same directory, not the profile directory.
Absolute paths and `~` are also supported.

Supported path templates:
- Shell: `{{flow.dir}}`, `{{runtime.cwd}}`, `{{runtime.python}}`, `{{runtime.venv}}`.
- Files: `{{flow.dir}}`, `{{runtime.cwd}}`, `{{runtime.venv}}`.

Other templates are invalid in tool permission paths. The `$VAR` expansion of
`config.file` does not apply to these permission fields. A template only names a
location; it does not grant access automatically.

### Shell permissions

- `tools.shell.allowed_paths`: permitted locations for `cwd` and command paths.
- Neither the flow directory nor the Runtime working directory is automatically
  permitted. Declare them explicitly when needed.
- Only the Runtime Python executable path is permitted automatically. This does
  not permit the entire venv or add Python to `allowed_commands`.
- `tools.shell.allowed_commands`: executable names permitted when
  `allowlist_enabled` is `true`. An empty command allowlist blocks execution.
- Path permission and command authorization are separate checks. Both must pass
  when the command allowlist is enabled.

For tool calls, omitted `cwd` uses the Runtime working directory; relative `cwd`
starts there too. The result must be permitted. Relative paths in the command
start at its effective `cwd`. The order of `allowed_paths` never selects `cwd`.
Use an explicit permitted absolute `cwd` when the Runtime working directory is
not allowed. Do not assume that tool-call arguments expand configuration templates.

### Files permissions

- `tools.files.read`: read access.
- `tools.files.write`: write and edit access.
- `tools.files.all`: read, write, and edit access.
- No paths are permitted automatically, including the flow directory and Runtime
  working directory.

Relative `files.path` arguments in tool calls start at the Runtime working
directory, not the flow or profile directory. Prefer concrete absolute paths
when these locations differ.

### Missing permissions and configuration writes

If no permitted alternative exists, ask the user to authorize a minimal change
in the effective configuration. Identify the selected profile and the exact
field/value needed; do not blindly edit a conventional `agent.json` that is not
being used. If the tools section is inherited from global settings, explain
whether the proposed change is global or a profile-specific override. Do not
broaden permissions, disable the allowlist, or edit a profile to bypass a denial.

Changing the model writes to the effective profile if that file contains `llm`;
otherwise it writes to the global configuration. A write failure does not
redirect the operation to a different file. A profile may be modified or
replaced when authorized permissions allow it; it is not immutable.
Do not use `AGENT_AGENT_CONFIG_FILE`; that process-wide override was removed.
An `export` or environment assignment in a shell child does not change the
Runtime parent's environment used to resolve `config.file`.
