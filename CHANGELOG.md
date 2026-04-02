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

## 1.0.0-alpha.7 - 2026-04-03

### Added
- Added skill validation with dedicated error codes, built-in skill coverage, and operator-facing docs for the skill checker.
- Added a dedicated run query read side and `/runs` support for compact waiting views in the CLI and TUI.
- Added local `cloudflared` tooling with `login`, `ensure`, `start`, `status`, and `stop`, plus dedicated operator docs.
- Added local server lifecycle tooling with explicit Skiller ownership tracking and dedicated operator docs.

### Changed
- Changed the TUI `/run` flow to follow runs incrementally instead of staying on the initial snapshot.
- Changed the `cloudflared ensure` flow to generate a tunnel config and publish the public hostname through tunnel ingress.
- Changed CLI operator output to use explicit ownership reporting via `managed_by_skiller`.
- Changed docs and backlog structure to reflect the current CLI/tooling surfaces and progress status.

### Fixed
- Fixed stale or reused PID handling for local server management so Skiller does not stop unrelated processes.
- Fixed public tunnel publication so `skillerwh.<domain>` resolves through the generated tunnel config instead of DNS routing alone.
- Fixed pytest collection conflicts between tool test modules that shared the same basename.

### Removed
- Removed the legacy `cloudflared` skill path in favor of CLI/tooling flow.

### Notes
- This release closes the current operator tooling pass around run inspection, local server lifecycle, and Cloudflare tunnel management.

## 1.0.0-alpha.6 - 2026-03-30

### Added
- Added the new `shell` step with support for `command`, `cwd`, `env`, `timeout`, `check`, and `large_result`.
- Added the default shell runner and runtime wiring needed to execute shell commands and scripts from skills.
- Added the `repo_checks` internal skill as a practical example that runs `ruff`, `pytest`, and `build` through the new `shell` step.
- Added unit, integration, and shell-based E2E coverage for the new `shell` feature.

### Changed
- Changed the TUI `/run` flow so synchronous successful runs render their completed step transcript instead of only the final success line.
- Changed the docs, README, and skill schema references to include the new `shell` step and the updated examples.

### Fixed
- Fixed the TUI output for completed runs so users can see the executed steps immediately after `/run`.

### Removed
- Nothing notable.

### Notes
- This release extends the runtime with shell execution while keeping large-output handling, transcript rendering, and CLI examples aligned.

## 1.0.0-alpha.5 - 2026-03-17

### Added
- Added a dedicated `Feature PR` GitHub Actions workflow for `feature/*` pull requests.
- Added repository scripts to validate PR branch shape and release metadata in CI.
- Added a reusable internal `pull_request` skill for opening both feature and release pull requests.

### Changed
- Changed release validation to run on `release/*` pull requests instead of a manual workflow on `main`.
- Changed release tagging so CI creates `v<version>` only after the release PR is merged.
- Changed `skiller-dev` to use a single workflow reference with explicit `[Agent]`, `[User]`, `[Admin]`, and `[Workflow]` responsibilities.

### Fixed
- Fixed the release instructions so the documented flow matches the active CI and pull request process.

### Removed
- Removed obsolete split release references from `skiller-dev` in favor of the consolidated workflow guide.

### Notes
- This release focuses on CI and release-process coherence after `v1.0.0-alpha.4`.

## 1.0.0-alpha.4 - 2026-03-16

### Added
- Added a worker-based CLI lifecycle with `worker start`, `worker run`, and `worker resume`.
- Added live CLI watch output so `skiller run` reports progress while the worker executes.
- Added GitHub MCP HTTP auth support with rendered `headers` and `{{env.*}}` templates.
- Added a manual GitHub Actions `Release` workflow for post-merge validation and tag creation.

### Changed
- Changed `skiller run` to create the run, launch the worker flow, and report progress instead of executing the full loop inline.
- Changed the runtime to use `RunWorkerService` as the canonical owner of step execution.
- Changed active docs and skill examples to English and trimmed legacy documentation from the repo.

### Fixed
- Fixed the webhook CLI flow to wait for the resumed worker instead of reading a transient `RUNNING` state.

### Removed
- Removed explicit external `run_id` injection from `skiller run`.
- Removed `RuntimeBootstrapService` as a separate layer and folded bootstrap into `RuntimeApplicationService`.

### Notes
- Established the worker-based execution path and live CLI watch output as the base runtime flow.

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
