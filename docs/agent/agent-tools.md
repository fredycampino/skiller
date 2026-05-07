# Agent Tools

This page documents the tool boundary used by the `agent` loop.

## Current Scope

Supported tools in the current slice:

- `shell`
- `notify`

## Boundary

`agent` does not execute tools directly. It delegates through `ToolManager`.

- `ToolManager`: validates allowlist and dispatches to configured tools
- `ToolAdapter`: validates raw args and builds typed tool requests
- `Tool`: executes capability and returns normalized `ToolResult`

## Constraints

`ToolManager` must not:

- update run state
- write `StepExecution`
- persist agent context entries directly
- know tool internals

Concrete tools must not know:

- YAML step shape
- `CurrentStep`
- `StepExecution`
- `next`
- transcript persistence policy

## Shell Policy Spec

`shell` policy configuration lives under runtime config (not in YAML `steps/agent`):

```json
{
  "shell": {
    "policy": {
      "allowlist": {
        "enabled": true,
        "workspace": "/home/fede/develop/py/skiller",
        "allow_env_prefix": true,
        "allowed_commands": ["ls", "cat", "rg", "git", "pytest"]
      },
      "sandbox": {
        "enabled": false
      }
    }
  }
}
```

### Rules

- `policy.allowlist.enabled` is boolean (`true` / `false`).
- `policy.allowlist.workspace` is a single workspace root path.
- `policy.allowlist.allowed_commands` is the executable allowlist.
- `policy.allowlist.allow_env_prefix` allows env prefixes like `FOO=1 BAR=2 cmd ...`.
- `policy.sandbox.enabled` is reserved for future sandbox execution.

When `allowlist.enabled` is `true`:

- each command segment (`&&`, `||`, `;`, `|`) must resolve to an executable present in
  `allowed_commands`
- if any segment is not allowed, the full command is rejected

When `allowlist.enabled` is `false`:

- allowlist executable filtering is skipped

Always enforced (independent from allowlist toggle):

- `ToolAdapter` argument validation (`command`, `cwd`, `env`, `timeout`)
- command-critical security blocking
- workspace path boundaries for `cwd` and command path candidates

### Future Sandbox

`policy.sandbox.enabled` is intentionally defined next to `allowlist` so sandboxing can be enabled
later without changing the external configuration shape.

## Related Docs

- [`../steps/agent.md`](../steps/agent.md)
- [`./agent-context.md`](./agent-context.md)
- [`./agent-event.md`](./agent-event.md)
