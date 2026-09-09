# `skiller config`

Displays the effective runtime configuration as JSON.

```bash
skiller config
```

The output includes the runtime, webhook, and effective `flow_paths` values.
Effective flow paths are ordered as the packaged `apps/agents` directory, the
runtime current working directory, and configured paths. Configuration is selected
using `AGENT_RUNTIME_CONFIG_FILE` when present, otherwise the default runtime
configuration file is used.
