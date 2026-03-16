# Skiller Runtime

Experimental skill runtime with current support for:
- `notify`
- `assign`
- `switch`
- `when`
- `llm_prompt`
- `mcp`
- `wait_webhook`

## Structure

- `src/skiller`: application code
- `skills`: declarative YAML/JSON skills
- `tests`: automated and manual verification
- `docs`: technical documentation for skills and steps

## Documentation

- `docs/guia_creacion_skills.md`
- `docs/steps/assign.md`
- `docs/steps/llm_prompt.md`
- `docs/steps/mcp.md`
- `docs/steps/notify.md`
- `docs/steps/switch.md`
- `docs/steps/wait_webhook.md`
- `docs/steps/when.md`

## Quickstart

Recommended command: `skiller`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Minimal internal skill
skiller run notify_test

# Branched demo skill
skiller run story_router --arg path=cave --arg mood=curious

# Demo skill with webhook + llm + switch
# Register the `signal` channel first
# skiller webhook register signal
skiller run webhook_signal_oracle --arg key=demo --start-webhooks

# llm_prompt skill using MiniMax
AGENT_LLM_PROVIDER=minimax \
AGENT_MINIMAX_API_KEY=your_api_key \
AGENT_MINIMAX_MODEL=MiniMax-M2.5 \
skiller run --file tests/e2e/skills/llm_prompt_cli_real_e2e.yaml --arg issue="Traceback auth failed"

# Manual E2E by step
./tests/e2e/cli_notify.sh
./tests/e2e/cli_assign.sh "dependency timeout"
./tests/e2e/cli_switch.sh "retry"
./tests/e2e/cli_when.sh
./tests/e2e/cli_llm_prompt.sh
./tests/e2e/cli_mcp_stdio.sh "hello-e2e"
./tests/e2e/cli_wait_webhook.sh 42
./tests/e2e/cli_all.sh

# External skill file
skiller run --file skills/notify_test.yaml

# Status and logs
skiller status <run_id>
skiller logs <run_id>

# Resume a run in WAITING
skiller resume <run_id>

# Inject a webhook for wait_webhook
skiller webhook receive github-pr-merged 42 --json '{"merged": true}' --dedup-key delivery-123

# Start the webhooks process when a run ends in WAITING
skiller run --file tests/e2e/skills/wait_webhook_cli_e2e.yaml --arg key=42 --start-webhooks

# Register and remove a webhook channel
skiller webhook register github-ci
skiller webhook remove github-ci
```

## Included Skills

Demo:
- `skills/story_router.yaml`
- `skills/webhook_signal_oracle.yaml`

Test and technical reference:
- `skills/notify_test.yaml`
- `skills/stdio_mcp_test.yaml`
- `skills/http_mcp_test.yaml`

## MCP

The source of truth for MCP connection settings lives in the skill YAML under the `mcp:` block.

Minimal examples:
- `stdio` in `skills/stdio_mcp_test.yaml`
- `streamable-http` in `skills/http_mcp_test.yaml`

## Available Commands

- `skiller init-db`
- `skiller run <skill> --arg key=value`
- `skiller run --file /path/to/skill.yaml --arg key=value`
- `skiller run ... --start-webhooks`
- `skiller resume <run_id>`
- `skiller status <run_id>`
- `skiller logs <run_id>`
- `skiller webhook register <webhook>`
- `skiller webhook remove <webhook>`
- `skiller webhook receive <webhook> <key> --json '{...}' --dedup-key <key>`
- `python -m skiller.tools.webhooks`

## Manual CLI E2E

Manual E2E flows live in `tests/e2e/cli_*.sh`.

- `cli_notify.sh`
- `cli_assign.sh`
- `cli_switch.sh`
- `cli_when.sh`
- `cli_llm_prompt.sh`
- `cli_mcp_stdio.sh`
- `cli_wait_webhook.sh`
- `cli_all.sh`

Each `cli_*.sh` uses an isolated temporary DB and removes it at the end so it does not leave garbage behind.
They intentionally do the minimum: run the real `skiller` commands and return a short JSON payload with `run_id` and `status`.
`cli_all.sh` consumes that output and prints a short `PASS/SKIP/FAIL` summary.

`cli_mcp_stdio.sh` validates the `mcp` step over `stdio` using an internal fixture from this repo.
It does not use `AGENT_MCP_LOCAL_MCP_*` and does not let the client control filesystem roots.
If you test against a real `local_mcp.py`, the `files_action` roots are resolved by the MCP server, not by env vars injected by `skiller`.

The old `test_*_e2e.py` files were removed so `pytest` does not mix stable automated coverage with manual or opt-in flows.
