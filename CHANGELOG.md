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
