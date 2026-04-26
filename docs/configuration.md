# Configuration

Skiller uses one persistent JSON configuration file:

```text
~/.skiller/settings/config.json
```

Use `AGENT_CONFIG_FILE=/path/to/config.json` only when a command needs a different config file.
Environment variables are still supported as command-level overrides, but Skiller does not load
`.env` files.

## Load Order

Skiller reads settings in this order:

1. environment variables
2. `AGENT_CONFIG_FILE=/path/to/config.json`
3. `~/.skiller/settings/config.json`
4. built-in defaults

## Example

```json
{
  "version": 1,
  "runtime": {
    "db_path": "~/.skiller/runtime.db",
    "log_level": "INFO"
  },
  "llm": {
    "default_provider": "minimax-fast",
    "providers": {
      "minimax-fast": {
        "type": "minimax",
        "api_key_file": "~/.skiller/secrets/minimax_api_key",
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M2.5",
        "timeout_seconds": 30
      },
      "fake-chat": {
        "type": "fake",
        "response_json": {
          "reply": "respuesta de prueba"
        },
        "model": "fake-llm"
      },
      "null": {
        "type": "null"
      }
    }
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

`llm.default_provider` selects one key from `llm.providers`.
For environment overrides, `AGENT_LLM_PROVIDER` can select either a configured provider name or a
built-in provider type such as `null`, `fake`, or `minimax`.

Provider profiles should define `type`. Supported provider types:

| Type | Description |
| --- | --- |
| `null` | disables `llm_prompt` calls |
| `fake` | returns a configured JSON response, useful for deterministic tests |
| `minimax` | calls the MiniMax chat completions API |

### MiniMax

| Field | Type | Default |
| --- | --- | --- |
| `type` | string | required |
| `api_key` | string | empty |
| `api_key_env` | string | empty |
| `api_key_file` | string | empty |
| `base_url` | string | `https://api.minimax.io/v1` |
| `model` | string | `MiniMax-M2.5` |
| `timeout_seconds` | number | `30` |

Prefer `api_key_file` so secrets stay outside the config file:

```json
{
  "type": "minimax",
  "api_key_file": "~/.skiller/secrets/minimax_api_key",
  "base_url": "https://api.minimax.io/v1",
  "model": "MiniMax-M2.5",
  "timeout_seconds": 30
}
```

MiniMax secret resolution order:

1. `AGENT_MINIMAX_API_KEY`
2. provider `api_key`
3. provider `api_key_env`
4. provider `api_key_file`

`api_key_file` supports `~` expansion.

### Fake

| Field | Type | Default |
| --- | --- | --- |
| `type` | string | required |
| `response_json` | object or string | `{"summary":"fake summary","severity":"low","next_action":"retry"}` |
| `model` | string | `fake-llm` |

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

## Environment Overrides

Environment variables are for one-off command overrides, CI, and tests. They are not loaded from
`.env` files.

| Environment variable | JSON field |
| --- | --- |
| `AGENT_CONFIG_FILE` | config file path |
| `AGENT_DB_PATH` | `runtime.db_path` |
| `AGENT_LOG_LEVEL` | `runtime.log_level` |
| `AGENT_LLM_PROVIDER` | `llm.default_provider` |
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
