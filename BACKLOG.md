# Backlog

## Follow-Up Cleanup

- Revisit `watch` and decide if the CLI should keep printing compact event text to `stderr` now that the UI consumes structured `events`.

- Consider whether `RUN_CREATE` and `RUN_RESUME` should eventually be rendered in a more explicit way in the transcript beyond the block header alone.

- Update the PR workflow instructions so agents must push the branch to `origin` before calling `skiller run pull_request`.

- Study how the UI should present step results more clearly for UX:
  - compact vs expanded result rendering
  - how to signal truncated outputs and `body_ref`
  - when to show structured `value` vs human `text`
  - whether some step types deserve custom rendering instead of the generic output block

## Logs And Debug

- Consider whether `/logs` needs future flags such as `--tail`, filtering by event type, or JSON-only formatting.

## `shell` Follow-Up

- Consider whether `shell` should stay shell-only or later split into:
  - `command` with structured `argv`
  - explicit interpreter selection

- Revisit safety boundaries for `shell`:
  - quoting rules
  - environment inheritance
  - timeouts
  - large output truncation policy

- Decide whether `shell` should eventually add:
  - explicit interpreter override
  - no-shell execution mode
  - stronger policy/sandbox integration

## `agent.yml` Exploration

- Study the viability of an `agent.yml` skill as a first-class runtime pattern.

- Start with a thin agent shape:
  - `wait_input`
  - `llm_prompt`
  - optional tool step
  - `notify`
  - loop or explicit finish

- Avoid turning it into a full agent framework too early.

- Clarify what an initial `agent.yml` should support:
  - multi-turn interaction
  - looped execution
  - short-term run state
  - transcript readability
  - optional tool use

- Identify missing prerequisites:
  - conversation/history accumulation strategy
  - state model for repeated turns
  - interaction with future `shell` step
  - boundaries between “skill” and “agent runtime”

- If viable, define:
  - a minimal example skill
  - expected event flow
  - expected transcript shape
  - constraints for first implementation

## DONE

- UI transcript moved to structured `events` only.

- Removed `events_text` fallback and raw watch text parsing from the TUI path.

- `/logs` defined as raw/debug output and rendered as pretty JSON in the TUI.

- Transcript headers standardized as:
  - `[run-create] skill:id4`
  - `[run-resume] skill:id4`

- Transcript step format standardized as:
  - `[step_type] step_id`

- Transcript became incremental by `event_id`, including create/resume block handling.

- Output wrapping improved:
  - preserved indentation on wrapped lines
  - wrapped long detail text by word instead of breaking inside words

- Status bar simplified to:
  - `Waiting → input`
  - `Waiting → webhook`

- Runtime event contract completed and adopted:
  - `RUN_CREATE`
  - `RUN_RESUME`
  - `STEP_STARTED`
  - `STEP_SUCCESS`
  - `STEP_ERROR`
  - `RUN_WAITING`
  - `RUN_FINISHED`

- `run.context.step_executions` became the persisted source of truth for runtime state.

- Runtime step execution model aligned in one cut:
  - `RunContext.step_executions`
  - `StepExecution`
  - typed `*Output` objects per step
  - normalized public `event.payload.output`

- `shell` step added in v1:
  - `command`, `cwd`, `env`, `timeout`, `check`, `large_result`
  - runtime shell resolution via `$SHELL`, `/bin/bash`, `/bin/sh`
  - `ShellOutput` with `ok`, `exit_code`, `stdout`, `stderr`
  - unit, integration, and CLI e2e coverage

- Large results support added:
  - persisted `execution_outputs`
  - `event.payload.output.body_ref`
  - optional `text_ref` for rebuilding full human text from stored bodies
  - `large_result: true` support in `mcp` and `llm_prompt`
  - UI body resolution via `/body` and transcript/status/log body loading

- Legacy runtime result contract removed:
  - no `run.context.results`
  - no `event.payload.result`
  - no `*Result` dataclasses by step

- State rehydration from observability events was removed.

- `webhook_registrations` ownership moved out of the state store and into `SqliteWebhookRegistry`.

- Wait persistence unified into a single `waits` table with `wait_type`.

- External resume payload storage unified into a single `external_events` table with `event_type`.

- `docs/db/schema.md` created and aligned with the current schema.

- Skill entrypoint made explicit with root `start: <step_id>`.

- Skill step syntax simplified to:
  - `- <step_type>: <step_id>`

- Hidden YAML conventions removed from authoring:
  - no mandatory `id: start`
  - no `id`
  - no `type`

- MCP step contract aligned with compact syntax:
  - step header `- mcp: <step_id>`
  - server field `server: <mcp_server_name>`

- Skills, e2e fixtures, integration fixtures, and step docs migrated to the new skill syntax.

- CLI command guide added and linked from `README.md`.

- Runtime/UI transcript behavior docs added and aligned:
  - `run_transcript.md`
  - `logs_debug.md`
  - related UI behavior docs
