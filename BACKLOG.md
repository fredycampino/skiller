# Backlog

## UI Transcript

- Commit the final visual reorder for transcript steps:
  - `[step_type] step_id`
  - example: `[switch] decide_exit`

- Remove remaining `events_text` fallback/rendering paths once the structured `events` contract is considered final.

- Review `tui_render.py` for dead helpers related to raw watch text parsing and remove what is no longer needed.

## Logs And Debug

- Define and document `/logs` explicitly as raw/debug output.

- Decide whether `events_text` should remain available only for debug compatibility or be removed entirely from the UI adapter path.

## Documentation

- Review consistency between:
  - `docs/events/runtime-events.md`
  - `docs/events/usecase-return-gap.md`
  - `docs/cli/command-guide.md`
  - `src/skiller/tools/ui/docs/behaviors/output_blocks.md`
  - `src/skiller/tools/ui/docs/behaviors/run_transcript.md`

- Add a short note clarifying:
  - transcript = user-facing execution view
  - `/logs` = debug/raw event stream

## Follow-Up Cleanup

- Revisit `watch` and decide if the CLI should keep printing compact event text to `stderr` now that the UI consumes structured `events`.

- Consider whether `RUN_CREATE` and `RUN_RESUME` should eventually be rendered in a more explicit way in the transcript beyond the block header alone.

## Step Model To Study

- Study whether the runtime should introduce an explicit `start` or `reset` step concept to simplify looped flows and make the transcript easier to understand.

- Evaluate whether this should be:
  - a runtime entry/reset rule
  - a real step type
  - or a transcript-only abstraction

- Clarify how this would affect:
  - looped skills like `chat`
  - the mandatory `id: start` rule
  - visible transcript semantics for repeated waiting states

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
  - shape of `event.payload.result`

- Define persistence expectations:
  - what goes into `run.context.results`
  - what goes into `event.payload.result`

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
