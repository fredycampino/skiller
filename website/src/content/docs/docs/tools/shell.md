---
title: Shell
description: Configure command and path checks for the agent shell tool.
---

The shell tool executes commands for the agent. Command allowlisting and path checks are independent; these settings do not configure the separate YAML shell step.

:::caution[Operational guardrails, not a sandbox]
Tool policies help prevent mistakes and provide actionable feedback to the agent. They are **not a security sandbox or an isolation boundary**, and an agent can bypass them, especially through interpreters or programs with broad capabilities.

Commands run with the operating-system permissions of the Skiller process. For untrusted tasks, use an unprivileged account and OS-level isolation, such as a restricted container, with filesystem, network, and resource limits.
:::

## Configure permissions

Enable the tool in the workflow and add its configuration to the tools section of the [agent profile](/docs/configuration/agent-profiles/) or [global agent configuration](/docs/configuration/global-agent/). See [Harness tools](/docs/tools/overview/) for selection and inheritance rules.

## Shell section shape

```json
{
  "tools": {
    "shell": {
      "allowed_paths": [
        "{{runtime.cwd}}"
      ],
      "allowlist_enabled": true,
      "allowed_commands": [
        "pwd",
        "ls",
        "cat"
      ],
      "allow_env_prefix": true,
      "expand_paths": true
    }
  }
}
```

## Fields

| Field | Description | Default |
| --- | --- | --- |
| `allowed_paths` | Permitted roots for the working directory and detected command paths. | `[]`, plus the active Python executable automatically |
| `allowlist_enabled` | Requires executable names to appear in allowed_commands. Path checks remain active either way. | `false` |
| `allowed_commands` | Allowed executable names when allowlisting is enabled. | `[]` |
| `allow_env_prefix` | Recognizes leading assignments such as MODE=test before locating the executable. | `true` |
| `expand_paths` | Expands supported environment and home references before checking command paths. | `true` |

## Command checks

With allowlisting enabled, every parsed command segment must use an allowed executable. For example, a pipeline using printf and cat needs both names. An empty command list blocks execution when allowlisting is enabled.

Use executable names, not full paths. Explicit executable paths must also pass path checks. Allowing Python's path does not add python to the command allowlist.

Disabling allow_env_prefix changes parsing, not the host shell's ability to assign environment variables. Disabling expand_paths skips unresolved expansion words during path checks; it does not stop shell expansion.

Heredocs require quoted or escaped delimiters, such as `<<'EOF'`. Their literal bodies are not inspected as commands.

## Command path expansion

With expand_paths enabled, path checks expand `$VAR`, `${VAR}`, `~`, and `~/path` using the Runtime environment plus the tool call's environment overrides. Home references such as `~user`, `~+`, and `~-` are unsupported by this check.

This expansion is for validation only: the original command is sent to the shell. It does not apply to permission-list entries, which use the templates below. With expand_paths disabled, unresolved expansion words are skipped during path checks; working-directory checks remain active.

## Allowed path templates

The allowed_paths permission lists accept the following templates. Skiller resolves them when loading tool configuration, not through the shell. Use the exact spelling shown, without spaces inside the braces.

| Template | Meaning |
| --- | --- |
| `{{flow.dir}}` | Directory containing the workflow YAML. |
| `{{runtime.cwd}}` | Directory where Skiller started. |
| `{{runtime.python}}` | Active Python executable. |
| `{{runtime.venv}}` | Active Python environment root. |

Templates can be used alone or with a subdirectory suffix. Any unrecognized template makes the configuration invalid; these lists do not accept arbitrary workflow expressions.

```json
{
  "tools": {
    "shell": {
      "allowed_paths": ["{{flow.dir}}/scripts", "{{runtime.cwd}}/output"]
    }
  }
}
```

These templates belong in permission configuration, not in the command or cwd supplied by the model. Allowing a template path does not add an executable to the command allowlist.

## Path resolution

Permission entries also accept absolute paths, `~` home paths, and paths relative to the flow YAML directory, regardless of where the profile is stored. Templates do not grant access unless included in a permission list.

A permitted directory includes its descendants. Resolved paths, including symlink targets, must remain within a permitted root.

An omitted tool-call cwd uses the Runtime working directory; a relative cwd also resolves from there. The directory must exist and be permitted. Relative command paths are checked from that effective working directory.

These checks cover the working directory and paths detected in the outer command, not all filesystem access performed by the executable.

## Defaults

Default configured values are:

```json
{
  "tools": {
    "shell": {
      "allowed_paths": [],
      "allowlist_enabled": false,
      "allowed_commands": [],
      "allow_env_prefix": true,
      "expand_paths": true
    }
  }
}
```

Only the active Python executable path is added automatically. Neither the working directory nor the flow directory is granted by default, so an ordinary working directory remains blocked until configured.
