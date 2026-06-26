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

After global and override files are combined, `llm` and `providers` are
required. A local override can contain only `llm.default_provider` when the
global file already provides the referenced provider.

The other root fields are optional and use mapper/model defaults.

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
    "max_turns": 30,
    "max_tool_calls": 10
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

Unknown root fields are ignored, except `agent`, which is explicitly rejected.
Unknown fields inside known sections are rejected.

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

## Providers

Provider entries live under the root `providers` object. The provider id is the
key, and the provider type is inferred from that key.

All providers require these common fields:

- `model`: selected model id
- `timeout_seconds`: request timeout
- `window_width_tokens`: provider context window used by Skiller unless
  `llm.window_width_tokens` overrides it for the selected provider

Supported provider/model combinations:

| Provider | Models | Credentials |
| --- | --- | --- |
| `null` | `null1` | none |
| `fake` | `model1` | none |
| `minimax` | `MiniMax-M2.5`, `MiniMax-M2.7` | `api_key`, `api_key_env`, or `api_key_file` |
| `lmstudio` | configured `models[]` entries | optional `api_key`, `api_key_env`, or `api_key_file` |
| `codex` | `gpt-5.4`, `gpt-5.5` | `credentials_file` |
| `bedrock` | `us.anthropic.claude-opus-4-6-v1`, `us.anthropic.claude-opus-4-7`, `us.anthropic.claude-opus-4-8`, `us.anthropic.claude-opus-4-5-20251101-v1:0`, `us.anthropic.claude-opus-4-1-20250805-v1:0`, `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.anthropic.claude-fable-5` | `profile` |

### Null

`null` is an internal no-op provider for local tests.

```json
{
  "providers": {
    "null": {
      "model": "null1",
      "timeout_seconds": 1,
      "window_width_tokens": 1000
    }
  }
}
```

### Fake

`fake` is an internal deterministic provider for tests.

```json
{
  "providers": {
    "fake": {
      "model": "model1",
      "timeout_seconds": 1,
      "window_width_tokens": 1000
    }
  }
}
```

### MiniMax

Accepted models:

- `MiniMax-M2.5`
- `MiniMax-M2.7`

Accepted credential fields:

- `api_key`
- `api_key_env`
- `api_key_file`

```json
{
  "providers": {
    "minimax": {
      "api_key_file": "~/.skiller/secrets/minimax_api_key",
      "model": "MiniMax-M2.7",
      "timeout_seconds": 60,
      "window_width_tokens": 80000
    }
  }
}
```

### LM Studio

LM Studio models are user-configured because local model identifiers depend on
the models installed in LM Studio.

Accepted fields:

- `base_url`: optional OpenAI-compatible base URL; defaults to
  `http://127.0.0.1:1234/v1`
- `api_key`, `api_key_env`, or `api_key_file`: optional
- `models`: required list of allowed local models

```json
{
  "providers": {
    "lmstudio": {
      "base_url": "http://127.0.0.1:1234/v1",
      "model": "mistralai/ministral-3-14b-reasoning",
      "models": [
        {
          "model": "mistralai/ministral-3-14b-reasoning",
          "context_window_tokens": 50000
        },
        {
          "model": "google/gemma-4-12b-qat",
          "context_window_tokens": 30000
        }
      ],
      "timeout_seconds": 120,
      "window_width_tokens": 50000
    }
  }
}
```

For LM Studio, keep `window_width_tokens` and each configured
`context_window_tokens` aligned with the model instance loaded in LM Studio
(`lms ps --json` shows `contextLength`). Skiller does not load or resize LM
Studio models; it only uses the OpenAI-compatible endpoint.

Example using an API key file:

```json
{
  "providers": {
    "lmstudio": {
      "api_key_file": "~/.skiller/secrets/lmstudio_api_key",
      "model": "google/gemma-4-12b-qat",
      "models": [
        {
          "model": "google/gemma-4-12b-qat",
          "context_window_tokens": 30000
        }
      ],
      "timeout_seconds": 120,
      "window_width_tokens": 30000
    }
  }
}
```

### Codex

Accepted models:

- `gpt-5.4`
- `gpt-5.5`

Accepted credential fields:

- `credentials_file`

```json
{
  "providers": {
    "codex": {
      "credentials_file": "~/.skiller/secrets/openai-codex.json",
      "model": "gpt-5.5",
      "timeout_seconds": 120,
      "window_width_tokens": 100000
    }
  }
}
```

The runtime owns fixed implementation details such as protocol, base URL, and
Codex headers.

### Bedrock

Accepted credential fields:

- `profile`

Use inference profile model IDs (for example `us.anthropic...`) instead of
direct model IDs.

```json
{
  "providers": {
    "bedrock": {
      "profile": "claude-bedrock",
      "model": "us.anthropic.claude-opus-4-6-v1",
      "timeout_seconds": 120,
      "window_width_tokens": 200000
    }
  }
}
```

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

There are two normal `agent.json` locations.

The global file is user-level config:

```text
~/.skiller/settings/agent.json
```

It should own shared provider credentials and defaults. This keeps secrets and
common model settings outside individual agents:

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
    "lmstudio": {
      "base_url": "http://127.0.0.1:1234/v1",
      "model": "mistralai/ministral-3-14b-reasoning",
      "models": [
        {
          "model": "mistralai/ministral-3-14b-reasoning",
          "context_window_tokens": 30000
        },
        {
          "model": "google/gemma-4-12b-qat",
          "context_window_tokens": 40000
        }
      ],
      "timeout_seconds": 120,
      "window_width_tokens": 50000
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

The local file is agent-level config:

```text
<flow-directory>/agent.json
```

For packaged agents, this is normally next to the flow `agent.yaml`, for example:

```text
packages/skiller/agents/mono/agent.yaml
packages/skiller/agents/mono/agent.json
```

The local file is optional. When present, it overrides the global file by root
section.

A local agent file can switch provider without repeating credentials when the
selected provider exists in the global `providers` section:

```json
{
  "llm": {
    "default_provider": "codex"
  }
}
```

A local agent file can also replace a full root section such as `tools`:

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

Root sections are not deep-merged. If the local file defines `tools`, it
replaces the full global `tools` section. If the local file defines `providers`,
it replaces the full global `providers` section.

Use this split as the default rule:

- global `agent.json`: credentials, provider definitions, shared defaults
- local `agent.json`: selected provider, loop limits, tool permissions for that
  specific agent

## Path Resolution

`agent.json` is not discovered from the process current working directory.
Only these sources are used:

- the global `~/.skiller/settings/agent.json`
- `AGENT_AGENT_CONFIG_FILE`, when set
- the `agent.json` passed by the current flow context, normally next to the
  current flow `agent.yaml`

Tool path settings are interpreted by each tool:

- `tools.shell.allowed_paths` entries are expanded and resolved when
  `agent.json` is loaded. Relative entries are resolved against the process
  current working directory at load time.
- `tools.files.read`, `tools.files.write`, and `tools.files.all` entries are
  expanded and resolved when a file request is checked. Relative entries are
  resolved against the process current working directory at request time.

Use absolute paths for stable global config. Use `.` only when the agent is
expected to run from the workspace root.

## Loop

```json
{
  "loop": {
    "max_turns": 30,
    "max_tool_calls": 10
  }
}
```

Fields:

- `loop.max_turns`: default max LLM decision turns for an `agent` step
- `loop.max_tool_calls`: max native tool calls accepted from one assistant response

Defaults:

- `loop.max_turns = 30`
- `loop.max_tool_calls = 10`

Env overrides:

- `AGENT_LOOP_MAX_TURNS`
- `AGENT_LOOP_MAX_TOOL_CALLS`

Step YAML `max_turns` and `max_tool_calls` override these values for that step.

## Context  (only dev)

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

## Agent Event Truncation

`event_output` truncates agent message, tool call, and tool result payloads
written to the runtime event log. It does not change step output values,
`output_value(...)`, the LLM context, or persisted agent context entries.

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

- `event_output.truncate.enabled`: enables or disables event payload truncation
- `event_output.truncate.max_text_chars`: max characters kept for text fields
- `event_output.truncate.max_json_chars`: max characters kept for JSON payloads
- `event_output.truncate.max_array_items`: max array items kept in event payloads

Defaults:

- `event_output.truncate.enabled = true`: truncation is enabled
- `event_output.truncate.max_text_chars = 600`: text fields keep up to 600 characters
- `event_output.truncate.max_json_chars = 4000`: JSON payloads keep up to 4000 characters
- `event_output.truncate.max_array_items = 20`: arrays keep up to 20 items

Env overrides:

- `AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED`
- `AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_JSON_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS`

Related event contract: [`./agent-event.md`](./agent-event.md).

## Tools

`tools` is optional.

`agent.json` can configure only tools that read runtime config. Current
configurable tools:

- `shell`
- `files`

### Tool Shell

`tools.shell` controls what the agent `shell` tool may execute. It restricts the
working directory, explicit path arguments, and optionally the executable names.

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

Fields:

- `tools.shell.allowed_paths`
- `tools.shell.allowlist_enabled`
- `tools.shell.allow_env_prefix`
- `tools.shell.allowed_commands`

`allowed_paths` defines the roots where shell `cwd` and explicit command path
arguments may point.

Defaults:

- `allowed_paths = ()`
- `allowlist_enabled = false`
- `allow_env_prefix = true`
- `allowed_commands = ()`

When `allowed_paths` is empty, the shell policy uses the process current
working directory as the effective allowed root.

### Tool Files

`tools.files` controls what the agent `files` tool may read or modify. Read and
write roots are independent, and `all` grants both permissions.

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

Fields:

- `tools.files.read`
- `tools.files.write`
- `tools.files.all`

Defaults:

- `read = ()`
- `write = ()`
- `all = ()`

`tools.files.all` grants both read and write access. `tools.files.read` only
grants read access. `tools.files.write` grants write and edit access.

When no files roots are configured, files actions are blocked.

Unknown tool config keys fail config mapping.

There are no tool env overrides in the current mapper.

## Validation Behavior

`validate_config` loads the same files and uses the same mapper as normal
runtime execution. Validation reports these categories:

- missing selected config file
- invalid JSON
- invalid schema, including unsupported fields inside known sections
- unsupported provider id
- missing selected default provider config
- unsupported provider model, including model env overrides
- missing required provider credential fields
- missing MiniMax API key source
- missing MiniMax `api_key_env` environment variable
- missing MiniMax `api_key_file`
- invalid env override values for booleans, positive integers, or positive numbers
- unknown tool config names
- invalid tool runtime config fields or value types

## Related Docs

- [`../config/config.md`](../config/config.md)
- [`./agent-context.md`](./agent-context.md)
- [`./agent-event.md`](./agent-event.md)
- [`./agent-tool-dev.md`](./agent-tool-dev.md)
- [`../steps/agent.md`](../steps/agent.md)
