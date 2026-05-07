# Configuration

Skiller uses one persistent JSON configuration file:

```text
~/.skiller/settings/config.json
```

For agent-specific runtime behavior, Skiller also supports:

```text
~/.skiller/settings/agent.json
```

Use `AGENT_CONFIG_FILE=/path/to/config.json` only when a command needs a different config file.
Use `AGENT_AGENT_CONFIG_FILE=/path/to/agent.json` only when a command needs a different
agent-specific config file.
Environment variables are still supported as command-level overrides, but Skiller does not load
`.env` files.

## Load Order

Skiller reads settings in this order:

1. environment variables
2. `AGENT_CONFIG_FILE=/path/to/config.json`
3. `~/.skiller/settings/config.json`
4. `AGENT_AGENT_CONFIG_FILE=/path/to/agent.json`
5. `~/.skiller/settings/agent.json`
6. built-in defaults

## Example

```json
{
  "version": 1,
  "runtime": {
    "db_path": "~/.skiller/runtime.db",
    "log_level": "INFO"
  },
  "webhooks": {
    "host": "127.0.0.1",
    "port": 8001
  },
  "whatsapp": {
    "bridge": {
      "host": "127.0.0.1",
      "port": 8002,
      "send_timeout_seconds": 10
    }
  },
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
  },
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

## Runtime

| Field | Type | Default |
| --- | --- | --- |
| `runtime.db_path` | string | `./runtime.db` |
| `runtime.log_level` | string | `INFO` |

`runtime.db_path` supports `~` expansion.

## LLM

LLM configuration is resolved only from `agent.json`.

## Webhooks

| Field | Type | Default |
| --- | --- | --- |
| `webhooks.host` | string | `127.0.0.1` |
| `webhooks.port` | integer | `8001` |

## WhatsApp

| Field | Type | Default |
| --- | --- | --- |
| `whatsapp.bridge.host` | string | `127.0.0.1` |
| `whatsapp.bridge.port` | integer | `8002` |
| `whatsapp.bridge.send_timeout_seconds` | number | `10` |

## Agent

`agent.json` is merged into `config.json` under the root `agent` key. Values from `agent.json`
override matching values from `config.json`.

For the dedicated agent view, see [`agent/agent-config.md`](agent/agent-config.md).

| Field | Type | Default |
| --- | --- | --- |
| `agent.event_output.truncate.enabled` | boolean | `true` |
| `agent.event_output.truncate.max_text_chars` | integer | `600` |
| `agent.event_output.truncate.max_json_chars` | integer | `4000` |
| `agent.event_output.truncate.max_array_items` | integer | `20` |
| `agent.event_output.pii.enabled` | boolean | `true` |
| `agent.event_output.secrets.enabled` | boolean | `true` |
| `shell.policy.allowlist.enabled` | boolean | `false` |
| `shell.policy.allowlist.workspace` | string | empty (`cwd` at startup) |
| `shell.policy.allowlist.allow_env_prefix` | boolean | `true` |
| `shell.policy.allowlist.allowed_commands` | list[string] | `[]` |
| `shell.policy.sandbox.enabled` | boolean | `false` |

Legacy compatibility:
- `agent.event_output.max_text_chars`
- `agent.event_output.max_json_chars`
- `agent.event_output.max_array_items`

These legacy keys are still accepted and map to `agent.event_output.truncate.*`.

## Environment Overrides

Environment variables are for one-off command overrides, CI, and tests. They are not loaded from
`.env` files.

| Environment variable | JSON field |
| --- | --- |
| `AGENT_CONFIG_FILE` | config file path |
| `AGENT_AGENT_CONFIG_FILE` | agent config file path |
| `AGENT_DB_PATH` | `runtime.db_path` |
| `AGENT_LOG_LEVEL` | `runtime.log_level` |
| `AGENT_LLM_PROVIDER` | `agent.json` `llm.default_provider` |
| `AGENT_FAKE_LLM_RESPONSE_JSON` | selected fake provider `response_json` |
| `AGENT_FAKE_LLM_MODEL` | selected fake provider `model` |
| `AGENT_MINIMAX_API_KEY` | selected MiniMax provider `api_key` |
| `AGENT_MINIMAX_BASE_URL` | selected MiniMax provider `base_url` |
| `AGENT_MINIMAX_MODEL` | selected MiniMax provider `model` |
| `AGENT_MINIMAX_TIMEOUT_SECONDS` | selected MiniMax provider `timeout_seconds` |
| `AGENT_WEBHOOKS_HOST` | `webhooks.host` |
| `AGENT_WEBHOOKS_PORT` | `webhooks.port` |
| `AGENT_WHATSAPP_BRIDGE_HOST` | `whatsapp.bridge.host` |
| `AGENT_WHATSAPP_BRIDGE_PORT` | `whatsapp.bridge.port` |
| `AGENT_WHATSAPP_BRIDGE_SEND_TIMEOUT_SECONDS` | `whatsapp.bridge.send_timeout_seconds` |
| `AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED` | `agent.event_output.truncate.enabled` |
| `AGENT_EVENT_OUTPUT_PII_ENABLED` | `agent.event_output.pii.enabled` |
| `AGENT_EVENT_OUTPUT_SECRETS_ENABLED` | `agent.event_output.secrets.enabled` |
| `AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS` | `agent.event_output.truncate.max_text_chars` |
| `AGENT_EVENT_OUTPUT_MAX_JSON_CHARS` | `agent.event_output.truncate.max_json_chars` |
| `AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS` | `agent.event_output.truncate.max_array_items` |
| `AGENT_SHELL_ALLOWLIST_ENABLED` | `shell.policy.allowlist.enabled` |
| `AGENT_SHELL_ALLOWLIST_WORKSPACE` | `shell.policy.allowlist.workspace` |
| `AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX` | `shell.policy.allowlist.allow_env_prefix` |
| `AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS` | `shell.policy.allowlist.allowed_commands` (comma-separated) |
| `AGENT_SHELL_SANDBOX_ENABLED` | `shell.policy.sandbox.enabled` |

## MCP

MCP servers are declared by each skill in the root `mcp` block. They are not configured through
`~/.skiller/settings/config.json`.

Use the skill-level `mcp` block for stable server definitions:

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py
```

See [`steps/mcp.md`](steps/mcp.md) and [`skills/skill-schema.md`](skills/skill-schema.md).

## File Safety

Keep both config and secret files outside the repository:

```text
~/.skiller/settings/config.json
~/.skiller/secrets/minimax_api_key
```

Restrict permissions for secret files:

```bash
chmod 600 ~/.skiller/secrets/minimax_api_key
```
