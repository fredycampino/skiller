# Agent Configuration

This document describes the current `agent.json` contract as implemented by:

- `JsonAgentConfig`
- `AgentConfigMapper`
- `AgentConfigModel`
- `AgentConfig`

## File Resolution

The runtime selects one agent config file. It does not merge files.

Resolution order:

1. `AGENT_AGENT_CONFIG_FILE`, when set
2. `agent.json` next to the current skill `agent.yaml`, when present
3. `~/.skiller/settings/agent.json`

If the selected file does not exist, config loading fails.

## Root Shape

`llm` is required. The other root fields are optional and use mapper/model defaults.

```json
{
  "llm": {
    "default_provider": "minimax-main",
    "providers": {
      "minimax-main": {
        "provider": "minimax",
        "client_type": "openai_chat_completions",
        "api_key_file": "~/.skiller/secrets/minimax_api_key",
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M2.5",
        "timeout_seconds": 30,
        "context_window_tokens": 1000000
      }
    }
  },
  "loop": {
    "max_turns": 10,
    "max_tool_calls": 5
  },
  "context": {
    "compaction": {
      "enabled": false,
      "max_total_tokens_ratio": 0.8
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

The root field `agent` is explicitly rejected.

## LLM

`llm.default_provider` is a logical key into `llm.providers`.

Each provider entry requires:

- `provider`
- `client_type`
- `model`
- `base_url`
- `timeout_seconds`
- `context_window_tokens`
- one API key source: `api_key`, `api_key_env`, or `api_key_file`

Provider entries are keyed by user-defined ids:

```json
{
  "llm": {
    "default_provider": "minimax-main",
    "providers": {
      "minimax-main": {
        "provider": "minimax",
        "client_type": "openai_chat_completions",
        "api_key_env": "AGENT_MINIMAX_API_KEY",
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M2.5",
        "timeout_seconds": 30,
        "context_window_tokens": 1000000
      }
    }
  }
}
```

Supported provider/model/client combinations:

| Provider | Client type | Models |
| --- | --- | --- |
| `null` | `null` | `null` |
| `fake` | `fake` | `fake`, `fake-llm` |
| `minimax` | `openai_chat_completions` | `MiniMax-M2.5`, `MiniMax-M2.7` |
| `openai` | `openai_chat_completions` | `gpt-5.2`, `gpt-5.2-mini` |

`provider` identifies the product/provider. `client_type` identifies the client protocol used to call it.

## LLM Env Overrides

These env vars are supported:

- `AGENT_LLM_PROVIDER`
- `AGENT_<PROVIDER>_API_KEY`
- `AGENT_<PROVIDER>_BASE_URL`
- `AGENT_<PROVIDER>_MODEL`
- `AGENT_<PROVIDER>_TIMEOUT_SECONDS`

Provider-specific env vars apply only to the selected provider.

Examples for `provider = "minimax"`:

- `AGENT_MINIMAX_API_KEY`
- `AGENT_MINIMAX_BASE_URL`
- `AGENT_MINIMAX_MODEL`
- `AGENT_MINIMAX_TIMEOUT_SECONDS`

Environment model overrides are validated against the supported model list.

## Loop

```json
{
  "loop": {
    "max_turns": 10,
    "max_tool_calls": 5
  }
}
```

Fields:

- `loop.max_turns`: default max LLM decision turns for an `agent` step
- `loop.max_tool_calls`: max native tool calls accepted from one assistant response

Defaults:

- `loop.max_turns = 10`
- `loop.max_tool_calls = 5`

Env overrides:

- `AGENT_LOOP_MAX_TURNS`
- `AGENT_LOOP_MAX_TOOL_CALLS`

Step YAML `max_turns` and `max_tool_calls` override these values for that step.

## Context

```json
{
  "context": {
    "compaction": {
      "enabled": false,
      "max_total_tokens_ratio": 0.8
    }
  }
}
```

Fields:

- `context.compaction.enabled`: reserved compaction flag
- `context.compaction.max_total_tokens_ratio`: ratio applied to the provider `context_window_tokens`

Defaults:

- `context.compaction.enabled = false`
- `context.compaction.max_total_tokens_ratio = 0.8`

There are no context env overrides in the current mapper.

## Event Output

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

Fields:

- `event_output.truncate.enabled`
- `event_output.truncate.max_text_chars`
- `event_output.truncate.max_json_chars`
- `event_output.truncate.max_array_items`

Defaults:

- `event_output.truncate.enabled = true`
- `event_output.truncate.max_text_chars = 600`
- `event_output.truncate.max_json_chars = 4000`
- `event_output.truncate.max_array_items = 20`

Env overrides:

- `AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED`
- `AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_JSON_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS`

The event output config is passed to agent event publishing when emitting agent messages, tool calls, and tool results.

## Tools

`tools` is optional.

The mapper only accepts keys for tools registered in the runtime container. Current registered agent tools:

- `shell`
- `notify`
- `files`

Only tools that implement `ConfiguredTool` read runtime config from `agent.json`.

Current state:

- `shell` supports runtime config
- `notify` does not read runtime config
- `files` supports runtime config

Valid shell config:

```json
{
  "tools": {
    "shell": {
      "workspace": "",
      "allowlist_enabled": false,
      "allow_env_prefix": true,
      "allowed_commands": []
    }
  }
}
```

Shell config fields:

- `tools.shell.workspace`
- `tools.shell.allowlist_enabled`
- `tools.shell.allow_env_prefix`
- `tools.shell.allowed_commands`

Shell config defaults:

- `workspace = ""`
- `allowlist_enabled = false`
- `allow_env_prefix = true`
- `allowed_commands = ()`

Valid files config:

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

Files config fields:

- `tools.files.read`
- `tools.files.write`
- `tools.files.all`

Files config defaults:

- `read = ()`
- `write = ()`
- `all = ()`

`tools.files.all` grants both read and write access. `tools.files.read` only grants read access. `tools.files.write` grants write and edit access.

Unknown tool config keys fail config mapping. Registered tools that do not implement `ConfiguredTool` do not read runtime config.

There are no tool env overrides in the current mapper.

## Validation Behavior

Config loading uses the provider and mapper above.

Config loading validates:

- missing selected config file
- invalid JSON
- invalid schema
- missing default LLM provider
- unsupported provider model
- unsupported provider/client pairing
- missing API key source
- missing API key env var
- missing API key file
- invalid env override values
- invalid tool runtime config

## Related Docs

- [`../config/config.md`](../config/config.md)
- [`./agent-context.md`](./agent-context.md)
- [`./agent-event.md`](./agent-event.md)
- [`./agent-tool-dev.md`](./agent-tool-dev.md)
- [`../steps/agent.md`](../steps/agent.md)
