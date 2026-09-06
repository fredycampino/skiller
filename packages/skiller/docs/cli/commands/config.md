# `skiller config`

Displays the effective runtime configuration as JSON.

```bash
skiller config
```

The output includes the runtime, webhook, and effective `flow_paths` values.
Effective flow paths include configured paths and the packaged `apps/agents`
directory. Configuration is selected using `AGENT_RUNTIME_CONFIG_FILE` when present,
otherwise the default runtime configuration file is used.
