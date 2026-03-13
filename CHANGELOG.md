# Changelog

All notable changes to this project should be summarized here before a version is cut from a `feature/*` branch into `main`.

## Unreleased

### Added
- Nothing yet.

### Changed
- Nothing yet.

### Fixed
- Nothing yet.

### Removed
- Nothing yet.

### Notes
- Update this section when a branch is ready for release.
- Summarize the branch at a functional level; do not turn this file into a commit log.

## 1.0.0-alpha.3 - 2026-03-13

### Added
- Added explicit `--run-id` support to `skiller run` so external callers can choose the run identifier before execution starts.
- Added a manual CLI E2E flow `tests/e2e/cli_run_id.sh` and included it in `tests/e2e/cli_all.sh`.

### Changed
- Moved run-id generation and validation into `StartRunUseCase` so the runtime always persists a final UUID decided before hitting the store.
- Simplified the state store contract so run creation always receives an effective `run_id` instead of generating one internally.
- Refreshed README manual E2E listings to include the explicit run-id flow.

### Fixed
- Made `skiller run --run-id ...` fail with a clear CLI error when the UUID is invalid or already exists.

### Removed
- Nothing notable.

### Notes
- `--run-id` now accepts only UUID values; when omitted, the runtime generates a new UUID automatically.

## 1.0.0-alpha.2 - 2026-03-12

### Added
- Added `switch` as a runtime step for exact-value routing by `step_id`.
- Added `when` as a runtime step for ordered conditional branching over a single value.
- Added manual CLI flows for `switch` and `when`, both included in `tests/e2e/cli_all.sh`.
- Added demo skills `story_router` and `webhook_signal_oracle` to showcase branching, webhook resume, and LLM-driven routing.

### Changed
- Closed the control-flow spike around `if` by formalizing `switch` and `when` as the branching primitives for `1.0.x`.
- Refreshed backlog, runtime flow docs, feature matrix, and testing rules to match the current branching model and manual CLI policy.
- Clarified in `skiller-dev` guidance that new runtime steps should ship with at least one manual CLI flow and an entry in `cli_all.sh`.
- Refreshed README examples to separate demo skills from technical test fixtures.

### Fixed
- Rebuilt persisted runtime context correctly from `SWITCH_DECISION` and `WHEN_DECISION` events.
- Kept manual CLI aggregation aligned with the actual runtime surface so new branching steps are exercised from the real entry point.

### Removed
- Nothing notable.

### Notes
- `switch` persists minimal routing output as `{"value": ..., "next": ...}` and emits `SWITCH_DECISION`.
- `when` persists minimal routing output as `{"value": ..., "next": ...}` and emits `WHEN_DECISION` with branch/operator metadata for traceability.
- `webhook_signal_oracle` requires registering the `signal` webhook channel before sending signed HTTP requests to the webhooks server.

## 1.0.0-alpha.1 - 2026-03-11

### Added
- Added runtime support for `llm_prompt` and `assign` steps.
- Added manual shell-based E2E CLI flows for `notify`, `assign`, `llm_prompt`, `mcp`, and `wait_webhook`.
- Added a focused store test to validate removal of the legacy `current_step` column.

### Changed
- Migrated runtime step progression to the `current` step-id pointer with explicit `start/next` flow.
- Unified step execution results across enabled runtime step types.
- Simplified manual MCP stdio validation to use an internal fixture instead of client-provided root overrides.
- Clarified sandbox test execution in the `skiller-dev` skill instructions.

### Fixed
- Restored reliable MCP `stdio` verification for local CLI flows.
- Made the manual `llm_prompt` CLI skip cleanly when MiniMax credentials are missing.

### Removed
- Removed the legacy `current_step` field from runtime state and SQLite persistence.
- Removed old Python CLI E2E tests replaced by manual shell flows.
- Removed fake client-side MCP root overrides from examples and operator docs.

### Notes
- For `local_mcp.py`, filesystem roots are controlled by the MCP server configuration, not by `skiller` client env injection.
