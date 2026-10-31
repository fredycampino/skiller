---
title: Files
description: Configure read, write, and edit permissions for the agent files tool.
---

The files tool reads, writes, and edits files. Read and write permissions are independent.

## Configure permissions

Enable the tool in the workflow and add its configuration to the tools section of the [agent profile](/docs/configuration/agent-profiles/) or [global agent configuration](/docs/configuration/global-agent/). See [Harness tools](/docs/tools/overview/) for selection and inheritance rules.

## Files section shape

```json
{
  "tools": {
    "files": {
      "read": [
        "{{runtime.cwd}}"
      ],
      "write": [],
      "all": []
    }
  }
}
```

## Fields

| Field | Description | Default |
| --- | --- | --- |
| `read` | Paths permitted for the read action. | `[]` |
| `write` | Paths permitted for write and edit actions; does not grant the separate read action. | `[]` |
| `all` | Paths permitted for all three actions. | `[]` |

The all grants are added to the corresponding read and write grants. There is no allowlist_enabled switch for files.

## Allowed path templates

The read, write, and all permission lists accept the following templates. Skiller resolves them when loading tool configuration, not through the shell. Use the exact spelling shown, without spaces inside the braces.

| Template | Meaning |
| --- | --- |
| `{{flow.dir}}` | Directory containing the workflow YAML. |
| `{{runtime.cwd}}` | Directory where Skiller started. |
| `{{runtime.venv}}` | Active Python environment root. |

Templates can be used alone or with a subdirectory suffix. Any unrecognized template makes the configuration invalid; these lists do not accept arbitrary workflow expressions.

```json
{
  "tools": {
    "files": {
      "read": ["{{flow.dir}}/reference"],
      "write": ["{{runtime.cwd}}/output"],
      "all": []
    }
  }
}
```

The files tool does not support `{{runtime.python}}`. Templates belong in the permission lists, not in the path supplied by the model when calling the tool.

## Path resolution

Permission entries also accept absolute paths, `~` home paths, and paths relative to the flow YAML directory, regardless of where the profile is stored. Templates do not grant access unless included in a permission list.

A permitted directory includes its descendants. Paths and symlink targets are resolved before checking the permitted roots.

Unlike relative permission entries, a relative path supplied in a tool call resolves from the Runtime working directory.

These permissions apply only to the files tool, not to shell commands or other programs.

## Defaults

```json
{
  "tools": {
    "files": {
      "read": [],
      "write": [],
      "all": []
    }
  }
}
```

No paths are granted automatically. With all three lists empty, every files action is blocked.
