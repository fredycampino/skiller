# Agent Configuration

This page documents agent-specific runtime configuration.

Config files:

```text
./agent.json
~/.skiller/settings/agent.json
```

`agent.json` is the primary user config file for agent-owned runtime features.

The runtime selects one agent config file. It does not merge `./agent.json` with
`~/.skiller/settings/agent.json`; the first existing source in the resolution order wins.

## Agent Loop

```json
{
  "agent": {
    "loop": {
      "max_turns": 10,
      "max_tool_calls": 5
    }
  }
}
```

### Fields

- `agent.loop.max_turns`
  - runner default for `agent` steps
  - a step YAML `max_turns` value overrides this for that step
- `agent.loop.max_tool_calls`
  - maximum native `tool_calls` accepted from one assistant response
  - a step YAML `max_tool_calls` value overrides this for that step
  - if the assistant returns more than this limit, the runtime appends corrective
    feedback to the agent context and asks the LLM again on the next turn

### Resolution Order

1. environment variables handled by the `AgentConfigPort` implementation
2. `AGENT_AGENT_CONFIG_FILE`
3. `./agent.json`
4. `~/.skiller/settings/agent.json`
5. adapter defaults in [`../../packages/skiller/src/skiller/infrastructure/config/agent_config_adapter.py`](../../packages/skiller/src/skiller/infrastructure/config/agent_config_adapter.py)

Current adapter defaults:

- `agent.loop.max_turns = 10`
- `agent.loop.max_tool_calls = 5`

## Agent Context Window

```json
{
  "agent": {
    "context": {
      "compaction": {
        "enabled": false,
        "max_total_tokens_ratio": 0.8
      }
    }
  }
}
```

### Fields

- `agent.context.compaction.enabled`
  - reserved for future summarization or compaction behavior
  - the current runner still uses a context window regardless of this flag
- `agent.context.compaction.max_total_tokens_ratio`
  - ratio applied to `llm.providers.<name>.context_window_tokens`
  - defines the maximum token window used when reading agent context for the next LLM request

Current adapter defaults:

- `agent.context.compaction.enabled = false`
- `agent.context.compaction.max_total_tokens_ratio = 0.8`

## Shell Tool Policy

```json
{
  "shell": {
    "policy": {
      "allowlist": {
        "enabled": true,
        "workspace": "~/projects/skiller",
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

### Fields

- `shell.policy.allowlist.enabled`
  - enables command allowlist enforcement
- `shell.policy.allowlist.workspace`
  - workspace root used by the shell tool
- `shell.policy.allowlist.allow_env_prefix`
  - allows `KEY=value cmd ...` prefixes before an allowed command
- `shell.policy.allowlist.allowed_commands`
  - allowlist of command names
- `shell.policy.sandbox.enabled`
  - reserved runtime flag for shell sandboxing

### Resolution Order

1. environment variables
2. `AGENT_AGENT_CONFIG_FILE`
3. `./agent.json`
4. `~/.skiller/settings/agent.json`
5. fallback shell config: [`../../packages/skiller/src/skiller/infrastructure/tools/shell/config.json`](../../packages/skiller/src/skiller/infrastructure/tools/shell/config.json)

Environment variables:

- `AGENT_SHELL_ALLOWLIST_ENABLED`
- `AGENT_SHELL_ALLOWLIST_WORKSPACE`
- `AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX`
- `AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS`
- `AGENT_SHELL_SANDBOX_ENABLED`

## LLM Providers

```json
{
  "llm": {
    "default_provider": "minimax",
    "providers": {
      "minimax": {
        "provider": "minimax",
        "client_type": "openai_chat_completions",
        "api_key_file": "~/.skiller/secrets/minimax_api_key",
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M2.5",
        "timeout_seconds": 30,
        "context_window_tokens": 1000000
      }
    }
  }
}
```

### Fields

- `llm.default_provider`
  - logical provider key selected by default
- `llm.providers.<name>.provider`
  - provider runtime type
- `llm.providers.<name>.client_type`
  - client implementation type used to call the provider API
- `llm.providers.<name>.api_key`
  - inline secret value
- `llm.providers.<name>.api_key_env`
  - environment variable name holding the secret
- `llm.providers.<name>.api_key_file`
  - file path containing the secret
- `llm.providers.<name>.base_url`
  - provider base URL
- `llm.providers.<name>.model`
  - provider model name
  - validated against the supported model list for `provider`
- `llm.providers.<name>.timeout_seconds`
  - request timeout
- `llm.providers.<name>.context_window_tokens`
  - maximum model context window used by context management

### Resolution Order

1. environment variables
2. `AGENT_AGENT_CONFIG_FILE`
3. `./agent.json`
4. `~/.skiller/settings/agent.json`

Environment variables:

- `AGENT_LLM_PROVIDER`
- `AGENT_FAKE_MODEL`
- `AGENT_MINIMAX_API_KEY`
- `AGENT_MINIMAX_BASE_URL`
- `AGENT_MINIMAX_MODEL`
- `AGENT_MINIMAX_TIMEOUT_SECONDS`

Model overrides from environment variables are validated after resolution. An unsupported
override fails config loading.

### Supported Provider Models

| Provider | Client type | Models |
| --- | --- | --- |
| `null` | `null` | `null` |
| `fake` | `fake` | `fake`, `fake-llm` |
| `minimax` | `openai_chat_completions` | `MiniMax-M2.5`, `MiniMax-M2.7` |
| `openai` | `openai_chat_completions` | `gpt-5.2`, `gpt-5.2-mini` |

`provider` identifies the product/provider. `client_type` identifies the protocol adapter used
to call it. A provider can use an OpenAI-compatible client without becoming an OpenAI provider.

## Agent Event Output Policy

```json
{
  "agent": {
    "event_output": {
      "truncate": {
        "enabled": true,
        "max_text_chars": 600,
        "max_json_chars": 4000,
        "max_array_items": 20
      }
    }
  }
}
```

### Fields

- `agent.event_output.truncate.enabled`
  - enables output truncation
- `agent.event_output.truncate.max_text_chars`
  - maximum text size before truncation
- `agent.event_output.truncate.max_json_chars`
  - maximum serialized JSON size before truncation
- `agent.event_output.truncate.max_array_items`
  - maximum array items kept in sanitized output

### Resolution Order

1. environment variables
2. `AGENT_AGENT_CONFIG_FILE`
3. `./agent.json`
4. `~/.skiller/settings/agent.json`
5. runtime defaults in [`../../packages/skiller/src/skiller/infrastructure/config/settings_model.py`](../../packages/skiller/src/skiller/infrastructure/config/settings_model.py)

## Legacy Compatibility

These keys are still accepted and map to `agent.event_output.truncate.*`:

- `agent.event_output.max_text_chars`
- `agent.event_output.max_json_chars`
- `agent.event_output.max_array_items`

Environment variables:

- `AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED`
- `AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_JSON_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS`

## Related Docs

- [`../configuration.md`](../configuration.md)
- [`./agent-event.md`](./agent-event.md)
