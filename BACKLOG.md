# Backlog

## Follow-Up Cleanup

- Revisit `watch` and decide if the CLI should keep printing compact event text to `stderr` now that the UI consumes structured `events`.

- Consider whether `RUN_CREATE` and `RUN_RESUME` should eventually be rendered in a more explicit way in the transcript beyond the block header alone.

## Logs And Debug

- Consider whether `/logs` needs future flags such as `--tail`, filtering by event type, or JSON-only formatting.

## Large Results

- Study a dedicated storage model for large step results.

- Prefer `event.payload.output.body_ref` over copying large payloads into runtime events.

- Evaluate whether large result bodies should remain in `run.context.step_executions` or move to a separate table such as `step_output_refs`.

- Define:
  - reference format
  - ownership
  - lifecycle and cleanup
  - interaction with transcript and `/logs`
  - relation to future steps such as `bash` and `agent.yml`

## New Step: `bash`

- Design and implement a `bash` step for local shell command execution.

- Define the YAML contract:
  - whether it uses `command`
  - or a safer structured `argv`
  - optional `cwd`
  - optional `env`
  - optional `timeout`
  - optional `check`

- Define the runtime result contract:
  - `ok`
  - `exit_code`
  - `stdout`
  - `stderr`
  - a short human-readable `text` for transcript/events

- Define the event contract for `bash`:
  - `STEP_STARTED`
  - `STEP_SUCCESS`
  - `STEP_ERROR`
  - shape of `event.payload.output`

- Define persistence expectations:
  - what goes into `run.context.step_executions`
  - what goes into `event.payload.output`

- Define safety boundaries:
  - shell vs no-shell execution
  - quoting rules
  - environment inheritance
  - timeouts
  - large output truncation policy

- Add documentation:
  - step reference in `docs/steps/bash.md`
  - examples in skills
  - mention in CLI/runtime docs if needed

- Add tests:
  - unit tests for step execution
  - integration tests with successful command
  - integration tests with non-zero exit
  - transcript/log rendering expectations

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
  - interaction with future `bash` step
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
