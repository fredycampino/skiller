# Agent Configuration Internals

The canonical user-facing reference for sections, fields, defaults, and examples
is [Global agent configuration](https://skiller.run/docs/configuration/global-agent/).
Provider configuration is documented in
[LLM providers](https://skiller.run/docs/configuration/llm-providers/).

This document retains profile resolution and implementation details. User-facing
profile documentation has not yet been moved to the website.

## File resolution

The user-level file is the base configuration:

```text
~/.skiller/settings/agent.json
```

The runtime applies at most one override file. The precedence is:

1. the file explicitly selected by the agent step's `config.file`, when declared;
2. otherwise, the `agent.json` next to the current flow, when present;
3. otherwise, only the user-level file.

The override is applied by root section. Sections are not deep-merged. For
example, a local `llm` section replaces the complete user-level `llm` section
and must contain both required fields.

`agent.json` is not discovered from the process current working directory.
Explicit references accept `$NAME`, `${NAME}`, and concatenations such as
`${PROFILE_DIR}/reviewer.json`. Variables come from the Runtime process environment
and must be present and non-empty. Expansion is performed once, without shell
execution or recursive expansion. `~` uses the Runtime home directory; relative
paths resolve from the current flow directory. Templates (`{{...}}`) are invalid.
An explicit missing or invalid profile fails instead of falling back to local or
global configuration. The selected file may be changed when permissions allow it;
the reference is resolved again for subsequent operations, including resume.

Changing the model writes to the selected profile when it contains `llm`, otherwise
to the global file. A write failure never redirects the operation to another file.

## Validation and legacy input handling

`JsonAgentConfigPort` loads the global configuration and applies the selected
profile by root section. `AgentConfigMapper` normalizes legacy input before
validating the resulting configuration with `AgentConfigModel`.

The mapper discards the legacy root `providers` section and
`llm.default_provider`. Neither supplies a provider/model selection. This is
implementation compatibility behavior, not a supported configuration example.

Loading fails for missing effective files, invalid JSON, missing required LLM
selection, other unknown fields, or invalid section values. Provider and model
availability is checked separately against the effective catalog.

## Execution limits

The mapper applies the existing loop and event-output environment overrides.
Agent step `max_turns` and `max_tool_calls` fields take precedence over resolved
loop settings in `StepConfigReader`. The scope and redundant controls of loop
configuration are tracked for follow-up review; this documentation cleanup does
not change execution behavior.

## Tools

`tools` contains runtime configuration for registered configurable tools. Tool
names and fields are validated, and relative paths are resolved against the
directory containing the current flow YAML (`{{flow.dir}}`), regardless of
whether the `tools` section comes from global, local, or external configuration.
Neither the flow directory nor `{{runtime.cwd}}` is automatically permitted;
permissions must be configured explicitly. Shell retains only the automatic
path permission for the runtime Python executable, without adding its command
to the executable allowlist.

See [`agent-config-tools.md`](./agent-config-tools.md) for the complete contract.

## Related implementation documentation

- [LLM adapters](./agent-config-llm.md)
- [Chat Completions reasoning](./completions-reasoning.md)
- [Bedrock thinking](./bedrock-thinking.md)
- [Context handling](./agent-context.md)
- [Context compaction](./agent-context-compaction.md)
- [Context pruning](./agent-context-prune.md)
- [Agent events](./agent-event.md)
- [Agent step](../steps/agent.md)
