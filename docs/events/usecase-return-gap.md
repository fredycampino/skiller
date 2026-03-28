# Use Case Return Gap

This document compares what each step use case returns today with:
- what must be persisted in `run.context.results`
- what must be emitted in `event.payload.result`

The goal is to keep execution state and observability aligned without making runtime state depend on event replay.

## Step Comparison

| Step Type | Current Use Case Return | Data Currently Available Inside Use Case | `run.context.results[step_id]` | `event.payload.result` |
|---|---|---|---|
| `wait_input` | `status`, `next_step_id`, `WaitInputResult` | `prompt`, resolved `payload`, `input_event_id`, `next` | `{"ok": true, "prompt": ..., "payload": ..., "input_event_id": ...}` when resolved | `{"prompt": ...}` while waiting, `{"prompt": ..., "payload": ..., "input_event_id": ...}` when resolved |
| `wait_webhook` | `status`, `next_step_id`, `WaitWebhookResult` | `webhook`, `key`, resolved payload, `next` | `{"ok": true, "webhook": ..., "key": ..., "payload": ...}` when resolved | `{"webhook": ..., "key": ...}` while waiting, `{"webhook": ..., "key": ..., "payload": ...}` when resolved |
| `switch` | `status`, `next_step_id`, `SwitchResult` | selected `next` | `{"value": ..., "next": ...}` | `{"next": ...}` |
| `when` | `status`, `next_step_id`, `WhenResult` | selected `next`, branch/op/right | `{"value": ..., "next": ..., "branch": ..., "op": ..., "right": ...}` | `{"next": ...}` |
| `llm_prompt` | `status`, `next_step_id`, `LlmPromptResult` | parsed output, model, `next` | full step result stored under `results[step_id]` | `{"text": ..., "json": ..., "model": ...}` |
| `notify` | `status`, `next_step_id`, `NotifyResult` | `message`, `next` | `{"message": ...}` | `{"message": ...}` |
| `assign` | `status`, `next_step_id`, `AssignResult` | assigned value/result, `next` | assigned value as stored by the step | `{"value": ...}` |
| `mcp` | `status`, `next_step_id`, `McpResult` | `ok/error`, raw result, server, tool, `next` | full step result stored under `results[step_id]` | `{"ok": ..., "text": ..., "error": ..., "data": ...}` |

## Context Vs Event Result

`run.context.results` and `event.payload.result` do not have the same responsibility.

`run.context.results`:
- is runtime state
- is consumed by later steps through expressions and path resolution
- may need richer step-specific data than the transcript needs
- must remain valid even if no events are replayed

`event.payload.result`:
- is an observability contract
- is consumed by `logs`, `watch`, and the UI transcript
- should be stable, minimal, and shaped for rendering
- should not be the source of truth for runtime rehydration

Rule:
- if a step exposes an outcome to users or operators, that outcome should appear in `event.payload.result`
- if a step needs richer internal state for later execution, that state belongs in `run.context.results`
- overlapping fields should stay semantically aligned

## Contract Gap

| Layer | Previous Gap | Current State |
|---|---|---|
| `StepExecutionResult` | only `status`, `next_step_id` | now returns `status`, `next_step_id`, `result` |
| `RunWorkerService` | relied on legacy step-specific events and exceptions | now emits `STEP_STARTED`, `STEP_SUCCESS`, `STEP_ERROR`, `RUN_WAITING`, `RUN_FINISHED` from one place |
| Runtime rehydration | rebuilt step results from events | now reads persisted `run.context.results` directly |
| Transcript consumers | mixed legacy events | now consume generic execution events with normalized `result` |

## Summary

- The use case return contract is now rich enough to support both runtime state and generic runtime events.
- `run.context.results` is the source of truth for execution state.
- `event.payload.result` is the source of truth for transcript/log rendering.
- The remaining design rule is to keep both representations aligned without forcing them to be identical.
