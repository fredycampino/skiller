---
title: Runtime configuration
description: Configure the runtime database, logging, webhook server, and workflow search paths.
---

Runtime configuration controls the database, logging, webhook server, and workflow search paths. By default, Skiller creates a minimal configuration at `~/.skiller/settings/config.json`.

Use `AGENT_RUNTIME_CONFIG_FILE` to select another existing file:

```bash
AGENT_RUNTIME_CONFIG_FILE=~/skiller-config.json skiller run @flows
```

## Configuration file

The configuration has the following structure:

```json
{
  "runtime": {
    "db_path": "~/.skiller/runtime/global.db",
    "log_level": "INFO"
  },
  "webhooks": {
    "host": "127.0.0.1",
    "port": 8001
  },
  "flow_paths": [
    "~/my-flows"
  ]
}
```

## runtime

Controls the database used to persist runs and events, and the runtime logging level.

| Field | Description | Default |
| --- | --- | --- |
| `db_path` | SQLite database for runs, events, and persisted state. | `~/.skiller/runtime/global.db` |
| `log_level` | Runtime logging level. | `INFO` |

The default database is shared across working directories. Existing databases elsewhere are not moved or merged automatically.

Use `AGENT_DB_PATH` to override the database path without changing the configuration file:

```bash
AGENT_DB_PATH=/tmp/skiller-test.db skiller run @flows
```

## webhooks

Sets the listening address and port of the local webhook server.

| Field | Description | Default |
| --- | --- | --- |
| `host` | Listening address. | `127.0.0.1` |
| `port` | Listening port. | `8001` |

Manage the server with:

```bash
skiller server start
skiller server status
skiller server stop
```

Restart the server after changing its host or port.

For external requests, use HTTPS and webhook authentication; see [Trigger an agent with a webhook](/docs/demos/agent-webhook/).

## flow_paths

Lists additional directories searched for workflow references such as `@helper`.

| Field | Description | Default |
| --- | --- | --- |
| `flow_paths` | Additional workflow search directories. | `[]` |

Keep agents in different directories:

```text
~/personal-agents/
└── helper/
    └── helper.yaml

~/work-agents/
└── reviewer/
    └── reviewer.yaml
```

Add both search directories to `flow_paths` in your configuration file:

```json
{
  "flow_paths": [
    "~/personal-agents",
    "~/work-agents"
  ]
}
```

Start either agent by name with `@`, without typing its full path:

```bash
skiller run @helper
skiller run @reviewer
```


