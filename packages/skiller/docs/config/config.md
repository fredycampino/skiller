# Config

## Precedence

```text
env -> explicit file -> local file -> global file -> default feature config.json
```

## env variables

Environment variables.

- runtime overrides
- highest priority
- useful for CI, local debugging, and one-off runs

## User file.json

User configuration files:

- `AGENT_AGENT_CONFIG_FILE`
  - explicit agent config path
  - highest priority file source for agent-owned config
- `./agent.json`
  - local agent config for the current workspace
  - selected instead of the global agent config when present
- `~/.skiller/settings/config.json`
  - general
  - must not contain config owned by other `.json` files
  - shared runtime settings
- `~/.skiller/settings/agent.json`
  - agent only
  - agent-specific user config
  - used only when no explicit or local agent config is selected
- `~/.skiller/settings/local.json`
  - server, tunnel, and local process config
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
| whatsapp bridge (`whatsapp.bridge.*`) | `config.json` | `../cli/tool-whatsapp.md` | implemented |
| agent loop (`agent.loop.*`) | `agent.json` | `../agent/agent-config.md`, `../steps/agent.md` | implemented |
| agent event output (`agent.event_output.*`) | `agent.json` | `../agent/agent-config.md` | implemented |
| shell tool policy (`shell.*`) | `agent.json` | `../agent/agent-config.md`, `../agent/agent-tools.md` | implemented |
| llm providers (`llm.*`) | `agent.json` | `../agent/agent-config.md` | implemented |
| local server / tunnels / local processes | `local.json` | `../cli/tool-server.md`, `../cli/tool-cloudflared.md`, `../cli/tool-whatsapp.md` | implemented |
