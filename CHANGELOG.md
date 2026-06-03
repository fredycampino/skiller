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

## 0.1.0-beta.2 - 2026-06-03

### Added
- Add configurable LLM context windows for agent runs.
- Add run end actions.

### Changed
- Refine agent runtime event construction and context handling.

### Fixed
- Keep agent event publishing out of infrastructure while preserving typed runtime event payloads.
- Improve oversized tool result handling for agent context.

### Notes
- Includes PR #55, PR #56, and PR #57.

## 0.1.0-beta.1 - 2026-06-01

### Added
- Add notify action domain models, completion handling, and open-url action rendering in the TUI.
- Add live run snapshot sync events and TUI run-level notices for updated and failed snapshot syncs.
- Add run query/status support and runtime database model documentation.

### Changed
- Rename skill checker/readiness code and docs to flow checker/readiness terminology.
- Update notify, status, flow, event, and database documentation for current runtime contracts.

### Fixed
- Keep completed notify actions hidden after action done events.
- Align TUI action button and transcript rendering with the typed notify action contract.

### Notes
- First public beta release from the reset `0.1.0` version line.
- Includes PR #51 and PR #53.

## 1.0.0-beta.9 - 2026-05-30

### Added
- Add shell `allowed_paths` runtime configuration for multiple permitted roots.

### Changed
- Replace shell `workspace` configuration with `allowed_paths` across agents, docs, tests, and runtime policy.
- Normalize shell allowed paths to `Path` values before runtime policy validation.
- Update Kawa prompt catalog language from shell workspace boundaries to allowed paths.

### Fixed
- Preserve tool result data in agent prompts while keeping text as a human preview.
- Allow path-based executables such as `./.venv/bin/python` to pass shell allowlist validation by executable name.

### Removed
- Remove public shell `workspace` configuration.

### Notes
- Includes PR #46 and PR #47.

## 1.0.0-beta.8 - 2026-05-28

### Added
- Add typed LLM provider/model domain objects and provider selection wiring.
- Add flow-oriented documentation pages and move legacy skill docs under flows.

### Changed
- Refine LLM model mapping and provider configuration validation.
- Update CLI, runtime, config, event, and agent documentation for current flow terminology.

### Fixed
- Improve OpenAI mapper coverage and Kawa shell command configuration tests.

### Notes
- Includes PR #43 and PR #44.

## 1.0.0-beta.7 - 2026-05-27

### Added
- Add Codex/OpenAI Responses LLM client support.
- Add Codex credential handling and Kawa agent configuration.

### Changed
- Require explicit model/provider configuration for agent LLM requests.
- Update agent configuration, prompt, and tool execution flows for provider-backed clients.

### Fixed
- Improve OpenAI Responses mapping and Codex credential verification coverage.

### Notes
- Includes PR #41.

## 1.0.0-beta.6 - 2026-05-26

### Added
- Add Codex device-code and OpenAI local-callback credential flows.
- Add TUI/runtime notify URL actions with action completion handling.
- Add agent file tools and local agent JSON configuration support.

### Changed
- Split runtime orchestration into runs, agents, and waits application services.
- Extend webhook registration to typed GET/query and POST/body_json configurations.
- Move architecture and code-style guidance into package documentation.

### Fixed
- Verify Codex credentials through streaming Responses-compatible requests.
- Improve TUI transcript rendering for waiting webhooks, finished runs, and step errors.

### Notes
- Includes PR #37, PR #38, and PR #39.

## 1.0.0-beta.5 - 2026-05-21

### Notes
- Rework agent runtime onboarding (PR #35).
