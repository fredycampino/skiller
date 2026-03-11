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
- `stdio mcp` through CLI with a real local MCP installation is a valid `e2e`.
  - make it opt-in through env/config, never by hardcoded machine paths in the repo
- MCP with test servers or repo fixtures belongs to `integration`.

## Placement

- `tests/unit/...`
- `tests/integration/...`
- `tests/e2e/...`

Keep fixtures near the integration tests that use them. Do not keep infrastructure fixtures under `tests/e2e/`.
