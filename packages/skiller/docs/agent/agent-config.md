# Agent Configuration

This page documents agent-specific runtime configuration.

Primary file:

```text
~/.skiller/settings/agent.json
```

`agent.json` is the primary user config file for agent-owned runtime features.

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
  - runtime default for `agent` steps
  - used when the step YAML does not define `max_turns`
- `agent.loop.max_tool_calls`
  - maximum native `tool_calls` accepted from one assistant response
  - not exposed in step YAML
  - if the assistant returns more than this limit, the runtime appends corrective
    feedback to the agent context and asks the LLM again on the next turn

### Resolution Order

1. environment variables
2. `~/.skiller/settings/agent.json`
3. fallback agent config: [`../../packages/skiller/src/skiller/infrastructure/agent/config.json`](../../packages/skiller/src/skiller/infrastructure/agent/config.json)

Current fallback values in [`../../packages/skiller/src/skiller/infrastructure/agent/config.json`](../../packages/skiller/src/skiller/infrastructure/agent/config.json):

- `agent.loop.max_turns = 10`
- `agent.loop.max_tool_calls = 5`

For `max_turns`, a step YAML value still overrides the runtime default for that specific step.

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
2. `~/.skiller/settings/agent.json`
3. fallback shell config: [`../../packages/skiller/src/skiller/infrastructure/tools/shell/config.json`](../../packages/skiller/src/skiller/infrastructure/tools/shell/config.json)

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
        "type": "minimax",
        "api_key_file": "~/.skiller/secrets/minimax_api_key",
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M2.5",
        "timeout_seconds": 30
      }
    }
  }
}
```

### Fields

- `llm.default_provider`
  - logical provider key selected by default
- `llm.providers.<name>.type`
  - provider runtime type
- `llm.providers.<name>.client_type`
  - optional explicit client override
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
- `llm.providers.<name>.timeout_seconds`
  - request timeout
- `llm.providers.fake.response_json`
  - fake provider response payload

### Resolution Order

1. environment variables
2. `~/.skiller/settings/agent.json`
3. fallback llm config: [`../../packages/skiller/src/skiller/infrastructure/llm/config.json`](../../packages/skiller/src/skiller/infrastructure/llm/config.json)

Environment variables:

- `AGENT_LLM_PROVIDER`
- `AGENT_FAKE_LLM_RESPONSE_JSON`
- `AGENT_FAKE_LLM_MODEL`
- `AGENT_MINIMAX_API_KEY`
- `AGENT_MINIMAX_BASE_URL`
- `AGENT_MINIMAX_MODEL`
- `AGENT_MINIMAX_TIMEOUT_SECONDS`

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
      },
      "pii": {
        "enabled": true
      },
      "secrets": {
        "enabled": true
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
- `agent.event_output.pii.enabled`
  - enables PII redaction
- `agent.event_output.secrets.enabled`
  - enables secret redaction

### Resolution Order

1. environment variables
2. `~/.skiller/settings/agent.json`
3. runtime defaults in [`../../packages/skiller/src/skiller/infrastructure/config/settings_model.py`](../../packages/skiller/src/skiller/infrastructure/config/settings_model.py)

## Legacy Compatibility

These keys are still accepted and map to `agent.event_output.truncate.*`:

- `agent.event_output.max_text_chars`
- `agent.event_output.max_json_chars`
- `agent.event_output.max_array_items`

Environment variables:

- `AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED`
- `AGENT_EVENT_OUTPUT_PII_ENABLED`
- `AGENT_EVENT_OUTPUT_SECRETS_ENABLED`
- `AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_JSON_CHARS`
- `AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS`

## Related Docs

- [`../configuration.md`](../configuration.md)
- [`./agent-event.md`](./agent-event.md)
