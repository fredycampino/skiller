# Runtime Config

This document describes the current `config.json` contract used by
`skiller.infrastructure.config.settings.get_settings()`.

`config.json` is still supported, but its scope is narrow: it configures
process-level runtime settings. Agent behavior, LLM providers, loop limits, and
agent tools are configured in [`agent.json`](../agent/agent-config.md).

## Location

Skiller reads runtime config from:

```text
~/.skiller/settings/config.json
```

Set `AGENT_CONFIG_FILE` to use an explicit file instead:

```bash
AGENT_CONFIG_FILE=/path/to/config.json skiller run mono
```

If `AGENT_CONFIG_FILE` points to a missing file, config loading fails. If the
global file is missing, Skiller uses defaults.

## Precedence

Runtime settings are resolved in this order:

```text
environment variables -> .env.development -> config.json -> built-in defaults
```

`config.json` does not override real environment variables or values loaded from
`.env.development`.

## `.env.development`

When present in the current working directory, `.env.development` provides local
development defaults after real environment variables and before `config.json`.

The repo development default is:

```bash
AGENT_DB_PATH=dev-runtime.db
```

This keeps local development runs away from the installed/global runtime DB.

## Schema

Current supported fields:

```json
{
  "runtime": {
    "db_path": "./runtime.db",
    "log_level": "INFO"
  },
  "webhooks": {
    "host": "127.0.0.1",
    "port": 8001
  }
}
```

Unknown top-level fields are ignored by the runtime settings loader.

## Runtime Settings

### `runtime.db_path`

SQLite runtime database path.

Environment override:

```bash
AGENT_DB_PATH=/path/to/runtime.db
```

Default:

```text
./runtime.db
```

### `runtime.log_level`

Log level used by the local server process.

Environment override:

```bash
AGENT_LOG_LEVEL=DEBUG
```

Default:

```text
INFO
```

## Webhook Settings

### `webhooks.host`

Host used by the local webhook/channel server.

Environment override:

```bash
AGENT_WEBHOOKS_HOST=127.0.0.1
```

Default:

```text
127.0.0.1
```

### `webhooks.port`

Port used by the local webhook/channel server.

Environment override:

```bash
AGENT_WEBHOOKS_PORT=8001
```

Default:

```text
8001
```

## Not In `config.json`

These settings are intentionally owned by other files:

| Area | File | Docs |
| --- | --- | --- |
| agent loop, providers, context, event output, tools | `agent.json` | [`agent-config.md`](../agent/agent-config.md) |
| flow-local agent overrides | `agent.json` next to `agent.yaml` | [`agent-config.md`](../agent/agent-config.md) |
