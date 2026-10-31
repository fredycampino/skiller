---
title: Harness tools
description: Enable agent tools and configure their permissions.
---

Harness tools let agents act on their environment. The workflow selects which tools the model can call; agent configuration defines their permissions.

:::caution[Operational guardrails, not a sandbox]
Tool policies help prevent mistakes and provide actionable feedback to the agent. They are **not a security sandbox or an isolation boundary**, and an agent can bypass them, especially through interpreters or programs with broad capabilities.

Commands run with the operating-system permissions of the Skiller process. For untrusted tasks, use an unprivileged account and OS-level isolation, such as a restricted container, with filesystem, network, and resource limits.
:::

## Enable tools

Declare tools on the agent step, alongside its task and system instructions:

```yaml
- agent: reviewer
  config:
    file: "~/.skiller/profiles/agent.reviewer.json"
  tools:
    - shell
    - files
```

Configuring permissions does not expose a tool by itself. The workflow must also enable it.

## Configure permissions

Add the tools section to the [agent profile](/docs/configuration/agent-profiles/) or to `~/.skiller/settings/agent.json`, the [global agent configuration](/docs/configuration/global-agent/).

If the profile defines tools, it replaces the entire global tools section, not individual tool fields. Otherwise, the global section applies. Missing settings use each tool's defaults; they do not grant unrestricted access.

```json
{
  "tools": {
    "shell": {
      "allowed_paths": ["{{runtime.cwd}}"],
      "allowlist_enabled": true,
      "allowed_commands": ["pwd", "ls", "cat"]
    },
    "files": {
      "read": ["{{runtime.cwd}}"],
      "write": [],
      "all": []
    }
  }
}
```

## Tool references

| Tool | Purpose | Permissions |
| --- | --- | --- |
| [Shell](/docs/tools/shell/) | Execute shell commands. | Command allowlist and checks on working directory and detected paths. |
| [Files](/docs/tools/files/) | Read, write, and edit files. | Separate read and write roots. |

Permissions belong to each tool. Files restrictions do not prevent an enabled shell command from reading or modifying files.

## Configuration validation

For Shell and Files, unknown configuration fields are rejected. Boolean fields require booleans; path and command lists require non-empty strings. Omitted or null fields inside a tool configuration use that field's defaults. This does not make the entire tools section nullable.

Tool configuration fields have no environment-variable overrides. Shell expansion inside a command is a separate mechanism.
