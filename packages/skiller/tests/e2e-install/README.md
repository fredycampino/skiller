# First-install E2E

Install the current wheel with pipx in Ubuntu 26.04 / Python 3.14, as a new
non-root user. No repository imports or host configuration are mounted.
Requires Docker, `uv`, internet access and `AGENT_MINIMAX_API_KEY` exported in the
calling environment. Never put the key in this directory or the Dockerfile.

From the repository root:

```bash
bash packages/skiller/tests/e2e-install/run.sh
```

The script builds only the current wheel in a temporary Docker build context.
It injects `AGENT_MINIMAX_API_KEY` at container runtime, not during image creation.
The clean home receives only a MiniMax selection and an `api_key_env`
reference; the secret is not written to configuration files.

Automated assertions:

1. Launch `@flows` from directory A. Runtime creates the global configuration,
   `~/.skiller/runtime/global.db` and `~/.skiller/settings/agent.flows.json`.
2. Send a task through the CLI. Assert a real `FIRST_INSTALL_OK` response and
   return to `WAITING`.
3. Launch `@flows` from directory B and query the previous run. Assert the
   same database inode, unchanged profile content/inode, and no other DBs.

This is a CLI first-install E2E, not a test of the STUI onboarding screens.
It makes a real, potentially billable MiniMax request. Use a test credential:
Flows has tools and the container has network access. The container is removed
on exit. The image contains no credentials, configuration or runtime database.
