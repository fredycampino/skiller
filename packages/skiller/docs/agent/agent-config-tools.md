# Agent Tool Configuration

This document describes the tools section of agent.json.

## Disclaimer: not a sandbox

> [!WARNING]
> Agent tool policies are **not a sandbox**. Treat them as a first line of
> protection against mistakes and as actionable feedback for the agent, not as
> an isolation boundary. A malicious agent could easily bypass these checks,
> especially through an interpreter or an executable with broad capabilities.
> Commands run with the operating-system permissions of the Skiller process.
> In sensitive environments, isolate the agent in a properly restricted
> container or sandbox, use an unprivileged user, restrict filesystem and
> network access, and apply resource limits to the complete process tree.

## Scope

tools is optional. agent.json can configure only tools that read runtime
configuration. Current configurable tools are:

- shell
- files

These contracts describe agent tools, not the separate YAML shell step policy.

## Shell

tools.shell checks the working directory and explicit command paths. It can
also restrict executable names. These are independent checks: disabling the
command allowlist does not disable path validation.

```json
{
  "tools": {
    "shell": {
      "allowed_paths": ["{{flow.dir}}", "{{runtime.venv}}"],
      "allowlist_enabled": false,
      "allowed_commands": [],
      "allow_env_prefix": true,
      "expand_paths": true
    }
  }
}
```

### allowed_paths

Type: list of non-empty path strings. Default configured value: empty list.

Adds permitted roots for the shell working directory (cwd) and paths detected
in the outer command. A permitted directory also permits its descendants.
Resolved paths, including symlink targets, must remain within a permitted root.

The runtime automatically adds only the active Python executable path
(`{{runtime.python}}`); configured paths are added to it and duplicates are
removed. The Runtime working directory, flow directory, and whole Python
environment are not automatically permitted. With no configured paths, an
ordinary working directory is therefore blocked, even though the Python
executable path is permitted.

Path checks remain active for both values of allowlist_enabled. There is no
switch in this configuration to disable them. They check paths detected in the
outer command, not filesystem access performed internally by programs, scripts,
or nested interpreters.

Accepted entries include absolute paths, `~`, paths relative to the flow
YAML directory, and these exact templates:

- `{{flow.dir}}`: directory containing the current flow YAML;
- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.python}}`: active Python executable;
- `{{runtime.venv}}`: active Python environment root.

Any other template is invalid. See Path Resolution below for the distinction
between configuration paths and tool-call paths.

### allowlist_enabled

Type: boolean. Default: false.

Controls **only executable-name validation against allowed_commands**:

- false: executable names are not restricted by allowed_commands.
- true: each parsed command segment must use an executable listed in
  allowed_commands. An empty list blocks execution.

It does not disable allowed_paths, working-directory validation, command
parsing, or heredoc validation. There is no built-in denylist of dangerous
commands.

| Check | false | true |
|---|---|---|
| Executable name in allowed_commands | Not required | Required |
| Working directory within allowed_paths | Required | Required |
| Detected command paths within allowed_paths | Required | Required |
| Quoted or escaped heredoc delimiter | Required | Required |

### allowed_commands

Type: list of non-empty strings. Default: empty list.

Lists executable names permitted when allowlist_enabled is true. When it is
false, this list has no effect.

Use executable names such as git, cat, or python, not full paths. The
policy compares the basename of the executable in each parsed segment. For
example, `printf 'hello' | cat` requires both printf and cat to be listed.
An executable invoked through an explicit path must also pass path validation.

Allowing the active Python executable path through allowed_paths does not
add its name to allowed_commands. Conversely, listing an executable name does
not grant access to its explicit path or its arguments' paths. Allowing an
interpreter delegates execution of its script to that interpreter; the list
does not inspect the script's internal operations.

### allow_env_prefix

Type: boolean. Default: true.

Controls how leading environment assignments are recognized when locating the
executable and checking paths in a command segment.

With true, a prefix such as `MODE=test` in `MODE=test git status` is recognized
as an assignment; git is the executable checked against allowed_commands.
Paths in recognized leading assignments are also checked against
allowed_paths.

With false, the policy does not skip these assignments when locating the
executable. If the allowlist is enabled, `MODE=test` is treated as the executable
name and normally fails that check. This setting does not rewrite the command
or disable environment assignments in the host shell. It does not control the
separate env argument of a tool call.

### expand_paths

Type: boolean. Default: true.

Does not grant permissions. Controls how command paths are checked against
allowed_paths:

- true: expands `$VAR`, `${VAR}`, `~`, and `~/path`, then checks the resulting
  paths against allowed_paths. Uses the Runtime environment plus tool-call env
  overrides. `~+`, `~-`, and `~user` are unsupported.
- false: checks literal paths only; words containing unresolved shell expansions
  are skipped.

The shell receives the original command and expands it normally. Working-directory
checks remain active. This field is independent of allowlist_enabled and
allowed_commands.

### Heredoc validation

Heredoc bodies are accepted only when the delimiter is quoted or escaped, such
as `<<'EOF'`, `<<"EOF"`, or `<<\EOF`. Their literal bodies are excluded from
command and path checks. Unquoted heredocs are rejected because Bash may execute
substitutions in their bodies. This validation applies independently of
allowlist_enabled and expand_paths.

## Files

tools.files controls what the agent files tool may read or modify. Read and
write roots are independent; all grants both permissions. There is no
allowlist_enabled field for this tool.

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

### read

Type: list of non-empty path strings. Default: empty list.

Grants read access to the listed paths and their descendants. It does not grant
write or edit access. A read is permitted through either read or all.

### write

Type: list of non-empty path strings. Default: empty list.

Grants write and edit access to the listed paths and their descendants. It does
not grant the separate read action. A write or edit is permitted through either
write or all.

### all

Type: list of non-empty path strings. Default: empty list.

Grants read, write, and edit access to the listed paths and their descendants.
These permissions are added to the corresponding read and write grants.

### Accepted file permission paths

All three fields accept absolute paths, `~`, paths relative to the flow YAML
directory, and these exact templates:

- `{{flow.dir}}`: directory containing the current flow YAML;
- `{{runtime.cwd}}`: directory where Skiller was started;
- `{{runtime.venv}}`: active Python environment root.

Any other template is invalid. Files grants no paths automatically. With all
three lists empty, files actions are blocked.

## Path Resolution

Tool permission paths are expanded and resolved when the configuration is
loaded. Relative entries resolve against the directory containing the current
flow YAML. `.` and `{{flow.dir}}` identify the same directory, whether tools
comes from the global config, a local config, or an external profile. A config
that defines tools replaces the whole global tools section, without changing
this base.

Templates do not grant permissions by themselves: paths must appear explicitly
in the corresponding permission lists, except for shell's automatic Python
executable path described above.

Tool-call paths have execution semantics, distinct from configuration entries:

- Relative files.path values resolve against the Runtime working directory.
- Missing or blank shell.cwd uses the Runtime working directory; relative
  cwd resolves against that directory, independently of allowed_paths order.
- The resolved shell working directory must be permitted, must exist, and must
  be a directory. An empty permission list never falls back to permitting it.
- Relative paths detected in shell commands resolve against the effective
  command working directory.

## Validation

Unknown tool configuration keys fail mapping. Boolean fields require booleans;
list fields require lists of non-empty strings. Omitted or null fields use
their defaults. There are no environment-variable overrides for tool
configuration fields in the current mapper; shell expansion of a tool call's
command is a separate operation.
