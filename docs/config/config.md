# Config

## Precedence

```text
env -> user file.json -> default feature config.json
```

## env variables

Environment variables.

- runtime overrides
- highest priority
- useful for CI, local debugging, and one-off runs

## User file.json

User configuration files:

- `~/.skiller/settings/config.json`
  - general
  - must not contain config owned by other `.json` files
  - shared runtime settings
- `~/.skiller/settings/agent.json`
  - agent only
  - agent-specific user config
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

- `src/skiller/infrastructure/tools/shell/config.py`
  - shell config resolver
- `src/skiller/infrastructure/tools/shell/config.json`
  - shell default values
- `src/skiller/infrastructure/llm/config.py`
  - llm config resolver
- `src/skiller/infrastructure/llm/config.json`
  - llm default values

## Features

| Feature | User file | Docs | Status |
| --- | --- | --- | --- |
| global runtime (`runtime.*`) | `config.json` | `docs/configuration.md` (legacy) | legacy |
| webhooks (`webhooks.*`) | `config.json` | `docs/configuration.md` (legacy) | legacy |
| whatsapp bridge (`whatsapp.bridge.*`) | `config.json` | `docs/configuration.md` (legacy) | legacy |
| agent loop (`agent.loop.*`) | `agent.json` | `docs/agent/agent-config.md`, `docs/steps/agent.md` | implemented |
| agent event output (`agent.event_output.*`) | `agent.json` | `docs/agent/agent-config.md` | implemented |
| shell tool policy (`shell.*`) | `agent.json` | `docs/agent/agent-config.md`, `docs/agent/agent-tools.md` | implemented |
| llm providers (`llm.*`) | `agent.json` | `docs/agent/agent-config.md` | implemented |
| local server / tunnels / local processes | expected: `local.json` | no dedicated doc yet | legacy |
