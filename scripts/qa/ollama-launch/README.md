# Ollama-launch QA environment

Manual QA of the local Skiller wheel installed with pipx in Ubuntu 26.04.
Requires Docker, `uv`, internet during build and access to Ollama on the LAN.

## Build and enter

From the repository root:

```bash
bash scripts/qa/ollama-launch/qa.sh build
```

Build opens an interactive shell. It does not replace an existing container.
After rebuilding, exit the shell and recreate an existing environment:

```bash
bash scripts/qa/ollama-launch/qa.sh reset
bash scripts/qa/ollama-launch/qa.sh start
```

Inside the container, start the dedicated agent:

```bash
skiller @qa
```

`start` first runs `skiller runs --limit 1` to initialize the Runtime through
its public CLI without auth, model calls or a fabricated database. STUI then
skips installation onboarding. Do not resume an old auth run: this environment
already has a provider configured. Reset removes any previous failed QA runs.

## One data volume

Only `scripts/qa/ollama-launch/data/` is mounted, writable, at `/data`:

| Host file, relative to this directory | Container path | Use |
| --- | --- | --- |
| `data/config.json` | `/data/config.json` | Runtime config with `flow_paths: ["/data/qa"]` |
| `data/providers.json` | `/data/providers.json` | Ollama provider and model configuration |
| `data/agent.json` | `/data/agent.json` | Explicit configuration of the QA agent |
| `data/qa/qa.yaml` | `/data/qa/qa.yaml` | Interactive `@qa` flow, without tools |
| `data/logs/llm.json` | `/data/logs/llm.json` | Latest native request and response |

The image sets `SKILLER_RUNTIME_CONFIG_FILE=/data/config.json` and
`SKILLER_AGENT_PROVIDERS_FILE=/data/providers.json`. The QA flow explicitly
selects `/data/agent.json`; no global agent configuration or symlink is needed.
The generated `~/.skiller/settings/agent.flows.json`, database and sessions
remain inside the container, not in the mounted data directory.

The supplied model is `hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K` on
`http://192.168.1.202:11434`, with context 32,768, output limit 4,096 and
`keep_alive: "5m"`. Agent effort is 3; its mapping sends `think: "medium"`.
Acceptance of thinking levels still needs real-server validation. No sampling
parameters are overridden. No server is installed, started or downloaded here.

Edit configuration from the host, then start a new QA run to reload it. Image
rebuilds are only needed for application or Dockerfile changes. Existing
containers must be recreated to acquire the new mount and environment variables.

Logs overwrite the previous request and may contain sensitive prompts or
responses. The logs directory is ignored by Git. No host home, secrets, whole
repository or Docker socket is mounted. The image uses the building user's UID
for write permissions; build and start as the same user.

## Persistence and reset

`exit` leaves the container and its processes running. `start` re-enters it,
restarting a stopped container if needed. `reset` permanently removes its
internal data, credentials, runs and database, after checking its ownership
label. It does not delete the image, mounted `data/`, or first-launch environment.
Changes made inside `/data` modify the host fixtures and persist across reset.

The container publishes no ports. Model requests are real and consume server
resources. This is not a sandbox for untrusted commands. pipx checks packaged
dependencies, not installation reproducibility from `uv.lock`.
