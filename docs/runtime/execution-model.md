# Execution Model

This document describes the main runtime components and how they fit together.

Core runtime responsibilities:
- `runs` store the persisted state of a run
- `waits` store active and resolved step waits
- `external_events` store inbound payloads that may resume a wait
- `events` store the generic runtime event stream used for observability

Waiting and resume matching are normalized around:
- `source_type`
- `source_name`
- `match_type`
- `match_key`

Current built-in mappings:
- `wait_channel`
  - `source_type = channel`
  - `source_name = <channel>`
  - `match_type = channel_key`
  - `match_key = <key>` or `all`
- `wait_input`
  - `source_type = input`
  - `source_name = manual`
  - `match_type = run`
  - `match_key = <run_id>`
- `wait_webhook`
  - `source_type = webhook`
  - `source_name = <webhook>`
  - `match_type = signal`
  - `match_key = <key>`

Main flow:
- create run
- prepare run
- worker renders current step
- current step executes and returns a structured result
- external events are stored as `pending` and consumed once by the selected run
- event lookup is scoped to the lifetime of the run:
  - events created before `run.created_at` are ignored
  - events created after `run.created_at` may resolve the wait, even if they arrived before the wait step
- matching is FIFO:
  - the oldest active wait wins
  - the oldest pending matching event is consumed first
- worker emits generic runtime events
- run reaches `WAITING`, `SUCCEEDED`, `FAILED`, or continues to the next step

Related docs:
- [`../skills/skill-schema.md`](../skills/skill-schema.md)
- [`../events/context-model.md`](../events/context-model.md)
- [`../events/runtime-events.md`](../events/runtime-events.md)
- [`../db/schema.md`](../db/schema.md)
