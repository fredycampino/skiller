# Agent Configuration

This document describes the current `agent.json` contract. The file selects an
LLM provider and model and configures agent runtime behavior. Provider
definitions, credentials, endpoints, and supported model lists do not belong in
`agent.json`; they are defined by the provider catalog documented in
[`agent-config-llm.md`](./agent-config-llm.md).

## File resolution

The user-level file is the base configuration:

```text
~/.skiller/settings/agent.json
```

The runtime applies at most one override file. The precedence is:

1. the file selected by `AGENT_AGENT_CONFIG_FILE`, when set;
2. otherwise, the `agent.json` next to the current flow, when present;
3. otherwise, only the user-level file.

The override is applied by root section. Sections are not deep-merged. For
example, a local `llm` section replaces the complete user-level `llm` section
and must contain both required fields.

`agent.json` is not discovered from the process current working directory.

## Root contract

`llm` is required. All other root sections are optional and use the defaults
described below. Unknown root fields and unknown fields inside known sections
are rejected.

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3"
  },
  "debug": {
    "log_request": false,
    "log_request_file": "~/.skiller/logs/request/minimax/request.json",
    "log_override_file": true
  },
  "loop": {
    "max_turns": 30,
    "max_tool_calls": 10
  },
  "context": {
    "window_width_tokens": 100000,
    "compaction": {
      "compaction_trigger_ratio": 0.8,
      "compaction_target_ratio": 0.5,
      "keep_last_blocks": 5
    }
  },
  "event_output": {
    "truncate": {
      "enabled": true,
      "max_text_chars": 600,
      "max_json_chars": 4000,
      "max_array_items": 20
    }
  },
  "tools": {}
}
```

## LLM selection

The `llm` section selects one provider and one of its supported models:

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3"
  }
}
```

Both fields are required, must be non-empty strings, and are resolved against
the effective provider catalog. Loading fails when the provider does not exist
or the selected model is not declared by that provider.

`llm.default_provider` is a tolerated legacy field. It is ignored and does not
replace either required field. This allows transitional files to retain the
old field while using the new `provider` and `model` selection:

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "default_provider": "minimax"
  }
}
```

A file containing only `default_provider` is invalid. The legacy root
`providers` section is also invalid. Move provider configuration to
`~/.skiller/settings/providers.json` or to the file selected by
`AGENT_PROVIDERS_FILE`.

## Global and flow-local selection

The user-level file can provide a default selection:

```json
{
  "llm": {
    "provider": "moonshot",
    "model": "kimi-k3"
  }
}
```

A flow-local file can replace that selection without repeating provider
credentials:

```json
{
  "llm": {
    "provider": "codex",
    "model": "gpt-5.6-luna"
  }
}
```

Credentials and provider runtime settings are resolved independently from the
provider catalog. See [`agent-config-llm.md`](./agent-config-llm.md).

## Debug

```json
{
  "debug": {
    "log_request": true,
    "log_request_file": "logs/llm-request.json",
    "log_override_file": true
  }
}
```

- `log_request` enables request logging. Default: `false`.
- `log_request_file` sets the destination. When omitted or empty, it defaults
  to `~/.skiller/logs/request/<provider>/request.json`.
- `log_override_file` replaces the destination on each request when `true`.
  Default: `true`.

## Loop

```json
{
  "loop": {
    "max_turns": 30,
    "max_tool_calls": 10
  }
}
```

Both values must be positive integers. Their defaults are `30` and `10`.

Environment overrides:

- `AGENT_LOOP_MAX_TURNS`
- `AGENT_LOOP_MAX_TOOL_CALLS`

Agent step fields `max_turns` and `max_tool_calls` override these values for
that step.

## Context

```json
{
  "context": {
    "window_width_tokens": 100000,
    "compaction": {
      "compaction_trigger_ratio": 0.8,
      "compaction_target_ratio": 0.5,
      "keep_last_blocks": 5
    }
  }
}
```

- `window_width_tokens` is an optional positive cap. When omitted, the selected
  model's native context window is used. The effective window never exceeds the
  model's declared context window.
- `compaction_trigger_ratio` must be greater than `0` and at most `1`.
  Default: `0.8`.
- `compaction_target_ratio` must be greater than `0`, at most `1`, and lower
  than the trigger ratio. Default: `0.5`.
- `keep_last_blocks` must be between `1` and `100`. Default: `5`.

There are no context environment overrides.

Related behavior is documented in
[`agent-context-compaction.md`](./agent-context-compaction.md) and
[`agent-context-prune.md`](./agent-context-prune.md).

## Agent event truncation

```json
{
  "event_output": {
    "truncate": {
      "enabled": true,
      "max_text_chars": 600,
      "max_json_chars": 4000,
      "max_array_items": 20
    }
  }
}
```

The three limits must be positive integers. Environment overrides:

- `AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED`
- `AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_JSON_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS`

Event truncation affects runtime event payloads. It does not change step output
values, LLM context, or persisted agent context entries. See
[`agent-event.md`](./agent-event.md).

## Tools

`tools` contains runtime configuration for registered configurable tools. Tool
names and fields are validated, and relative paths are resolved against the
directory containing the effective `agent.json` section.

See [`agent-config-tools.md`](./agent-config-tools.md) for the complete contract.

## Validation

Configuration loading fails for:

- a missing effective configuration file;
- invalid JSON;
- missing `llm.provider` or `llm.model`;
- unknown fields other than the tolerated `llm.default_provider` legacy field;
- an unknown provider or a model not supported by that provider;
- invalid loop, context, event output, debug, or tool values.

Provider catalog validation, adapter fields, credentials, and merge rules are
documented in [`agent-config-llm.md`](./agent-config-llm.md).

## Related documentation

- [`agent-config-llm.md`](./agent-config-llm.md)
- [`agent-config-tools.md`](./agent-config-tools.md)
- [`agent-context.md`](./agent-context.md)
- [`agent-event.md`](./agent-event.md)
- [`../config/config.md`](../config/config.md)
- [`../steps/agent.md`](../steps/agent.md)
