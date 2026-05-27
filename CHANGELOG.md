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
