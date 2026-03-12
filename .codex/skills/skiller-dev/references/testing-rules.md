# Testing Rules

## Test Types

- `unit`
  - tests one piece in isolation
  - no real infrastructure
  - no external process
  - no real network
  - no real database

- `integration`
  - crosses real components of the system
  - may use fixtures
  - may use subprocesses
  - may use a temporary real database
  - may use local HTTP servers or test MCP servers

- `e2e`
  - enters through a real system interface
  - typically CLI or HTTP
  - no infrastructure fixtures from the repo
  - validates an observable final result
  - keep these few and high-value

## Classification Rule

- If a test needs infrastructure fixtures, it is not `e2e`.
- If a scenario is already well covered in `integration`, do not duplicate it in `e2e`.
- In `e2e`, less is more.

## Current Repo Intent

- `notify` through CLI is a valid `e2e`.
- `assign`, `switch`, `when`, `wait_webhook`, and `llm_prompt` through CLI are valid manual operator flows.
- `llm_prompt` CLI remains opt-in when it depends on real provider credentials.
- `stdio mcp` through CLI is part of the manual CLI coverage in this repo.
- MCP with test servers or repo fixtures belongs to `integration`.
- Manual CLI wrappers live in `tests/e2e/cli_*.sh`.
- `tests/e2e/cli_all.sh` is the manual aggregator for those flows.
- When adding a new runtime step intended for real usage, add at least one `cli_<step>.sh` flow and register it in `cli_all.sh`.

## Placement

- `tests/unit/...`
- `tests/integration/...`
- `tests/e2e/...`

Keep fixtures near the integration tests that use them. Do not keep infrastructure fixtures under `tests/e2e/`.
Small YAML skills used only by manual CLI wrappers may live under `tests/e2e/skills/`.
