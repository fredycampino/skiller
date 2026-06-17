# Agent Configuration

This document describes the current `agent.json` contract as implemented by:

- `JsonAgentConfig`
- `AgentConfigMapper`
- `AgentConfigModel`
- `AgentConfig`

## File Resolution

The runtime always uses the global config as the base when it exists:

```text
~/.skiller/settings/agent.json
```

Then it applies one optional override file.

Override resolution order:

1. `AGENT_AGENT_CONFIG_FILE`, when set
2. `agent.json` next to the current flow `agent.yaml`, when present

Overrides are applied by root section. There is no deep merge inside a section.
For example, an override containing `tools` replaces the full global `tools`
section. Provider definitions live in the root `providers` section, so an agent
can override only `llm.default_provider` without repeating credentials.

If neither the global config nor an override file exists, config loading fails.

## Root Shape

`llm` and `providers` are required. The other root fields are optional and use
mapper/model defaults.

```json
{
  "llm": {
    "default_provider": "minimax"
  },
  "providers": {
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key",
      "model": "MiniMax-M2.5",
      "timeout_seconds": 30,
      "window_width_tokens": 1000000
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

`llm.default_provider` is a logical key into the root `providers` section.

`llm.window_width_tokens` is optional. When present, it is the effective window
width for the selected provider. When absent, the selected provider uses its own
`window_width_tokens`.

Each provider entry requires:

- `model`
- `timeout_seconds`
- `window_width_tokens`
- credentials required by that provider

Provider entries are keyed by the logical provider id:

```json
{
  "llm": {
    "default_provider": "minimax",
    "window_width_tokens": 80000
  },
  "providers": {
    "minimax": {
      "api_key_env": "AGENT_MINIMAX_API_KEY",
      "model": "MiniMax-M2.5",
      "timeout_seconds": 30,
      "window_width_tokens": 1000000
    }
  }
}
```

In this example the provider declares `1000000` tokens, but this agent uses
`80000` as its effective context limit before applying
`context.compaction.max_total_tokens_ratio`.

Supported provider/model combinations:

| Provider | Models | Credentials |
| --- | --- | --- |
| `null` | `null1` | none |
| `fake` | `model1` | none |
| `minimax` | `MiniMax-M2.5`, `MiniMax-M2.7` | `api_key`, `api_key_env`, or `api_key_file` |
| `codex` | `gpt-5.4`, `gpt-5.5` | `credentials_file` |
| `bedrock` | `us.anthropic.claude-opus-4-6-v1`, `us.anthropic.claude-opus-4-7`, `us.anthropic.claude-opus-4-8`, `us.anthropic.claude-opus-4-5-20251101-v1:0`, `us.anthropic.claude-opus-4-1-20250805-v1:0`, `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.anthropic.claude-fable-5` | `profile` |

The runtime owns fixed implementation details such as protocol, base URL, and Codex headers.
For Bedrock, use inference profile model IDs (for example `us.anthropic...`) instead of direct model IDs.

## LLM Env Overrides

These env vars are supported:

- `AGENT_LLM_PROVIDER`
- `AGENT_<PROVIDER>_API_KEY`
- `AGENT_<PROVIDER>_MODEL`
- `AGENT_<PROVIDER>_TIMEOUT_SECONDS`

Provider-specific env vars apply only to the selected provider.

Examples for `provider = "minimax"`:

- `AGENT_MINIMAX_API_KEY`
- `AGENT_MINIMAX_MODEL`
- `AGENT_MINIMAX_TIMEOUT_SECONDS`

Environment model overrides are validated against the supported model list.

## Global And Agent Overrides

The global file should own shared provider credentials and defaults:

```json
{
  "llm": {
    "default_provider": "minimax"
  },
  "providers": {
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key",
      "model": "MiniMax-M2.7",
      "timeout_seconds": 60,
      "window_width_tokens": 80000
    },
    "codex": {
      "credentials_file": "~/.skiller/secrets/openai-codex.json",
      "model": "gpt-5.5",
      "timeout_seconds": 120,
      "window_width_tokens": 100000
    },
    "bedrock": {
      "profile": "claude-bedrock",
      "model": "us.anthropic.claude-opus-4-6-v1",
      "timeout_seconds": 120,
      "window_width_tokens": 200000
    }
  }
}
```

An agent can switch provider without repeating credentials:

```json
{
  "llm": {
    "default_provider": "codex"
  }
}
```

An agent can also replace a full root section such as `tools`:

```json
{
  "tools": {
    "shell": {
      "allowed_paths": ["."],
      "allowlist_enabled": true,
      "allow_env_prefix": true,
      "allowed_commands": ["pwd", "ls", "rg"]
    }
  }
}
```

Because overrides are root-section based, defining `providers` in an agent file
replaces the full global `providers` section.

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
- `context.compaction.max_total_tokens_ratio`: ratio applied to `llm.window_width_tokens`
  when present, otherwise to the selected provider `window_width_tokens`

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
      "allowed_paths": ["."],
      "allowlist_enabled": false,
      "allow_env_prefix": true,
      "allowed_commands": []
    }
  }
}
```

Shell config fields:

- `tools.shell.allowed_paths`
- `tools.shell.allowlist_enabled`
- `tools.shell.allow_env_prefix`
- `tools.shell.allowed_commands`

`allowed_paths` defines the roots where shell `cwd` and explicit command path
arguments may point.

Shell config defaults:

- `allowed_paths = ["."]`
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
