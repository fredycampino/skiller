# Agent Configuration Internals

The canonical user-facing reference for sections, fields, defaults, and examples
is [Global agent configuration](https://skiller.run/docs/configuration/global-agent/).
Provider configuration is documented in
[LLM providers](https://skiller.run/docs/configuration/llm-providers/).

Profile selection, inheritance, path references, and model changes are documented
in [Agent profiles](https://skiller.run/docs/configuration/agent-profiles/).
This document covers implementation responsibilities and compatibility behavior.

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

## Execution configuration

`AgentConfigMapper` applies the loop and event-output environment overrides.
`StepConfigReader` applies agent-step execution overrides after configuration
loading. User-facing limits are documented in
[Harness loop limits](https://skiller.run/docs/configuration/harness-loop-limits/).

Tool payload mapping is delegated to registered tool runtime configuration
mappers. See [Tool configuration internals](./agent-config-tools.md) for the
implementation and [Harness tools](https://skiller.run/docs/tools/overview/)
for configuration and permissions.

## Related implementation documentation

- [LLM adapters](./agent-config-llm.md)
- [Chat Completions reasoning](./completions-reasoning.md)
- [Bedrock thinking](./bedrock-thinking.md)
- [Context handling](./agent-context.md)
- [Context compaction](./agent-context-compaction.md)
- [Context pruning](./agent-context-prune.md)
- [Agent events](./agent-event.md)
- [Agent step](../steps/agent.md)
