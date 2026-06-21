# Config

## Precedence

```text
env -> .env.development -> explicit file -> flow-local file -> global file -> default feature config.json
```

## env variables

Environment variables.

- runtime overrides
- highest priority
- useful for CI, local debugging, and one-off runs

## `.env.development`

When present in the current working directory, `.env.development` provides local
development defaults after real environment variables and before JSON config files.

The repo development default is:

```bash
AGENT_DB_PATH=dev-runtime.db
```

This keeps local development runs away from the installed/global runtime DB.

## User file.json

User configuration files:

- `AGENT_AGENT_CONFIG_FILE`
  - explicit agent config path
  - highest priority file source for agent-owned config
- `agent.json` next to the current flow `agent.yaml`
  - flow-local agent config
  - selected instead of the global agent config when present
- `~/.skiller/settings/config.json`
  - general
  - must not contain config owned by other `.json` files
  - shared runtime settings
- `~/.skiller/settings/agent.json`
  - agent only
  - agent-specific user config
  - used only when no explicit or flow-local agent config is selected
- `~/.skiller/settings/local.json`
  - server and local process config
  - machine-local runtime config

## Default config.json feature

The fallback is defined per feature.

It lives in infrastructure next to the feature `config.py`, which knows how to interpret it.

- versioned fallback shipped with the code
- used when the user did not override that feature
- owned by one feature only

Example:

- `packages/skiller/src/skiller/infrastructure/tools/shell/config.py`
  - shell config resolver
- `packages/skiller/src/skiller/infrastructure/tools/shell/config.json`
  - shell default values

## Features

| Feature | User file | Docs | Status |
| --- | --- | --- | --- |
| global runtime (`runtime.*`) | `config.json` | this document | implemented |
| webhooks (`webhooks.*`) | `config.json` | `../cli/tool-server.md` | implemented |
| agent loop (`loop.*`) | `agent.json` | `../agent/agent-config.md`, `../steps/agent.md` | implemented |
| agent event output (`event_output.*`) | `agent.json` | `../agent/agent-config.md` | implemented |
| shell tool policy (`tools.shell.*`) | `agent.json` | `../agent/agent-config.md`, `../agent/agent-tools.md` | implemented |
| llm providers (`llm.*`) | `agent.json` | `../agent/agent-config.md` | implemented |
| local server / local processes | `local.json` | `../cli/tool-server.md` | implemented |
