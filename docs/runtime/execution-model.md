# Execution Model

This document describes the main runtime components and how they fit together.

Core runtime responsibilities:
- `runs` store the persisted state of a run
- `waits` store active and resolved step waits
- `external_events` store inbound payloads that may resume a wait
- `events` store the generic runtime event stream used for observability

Main flow:
- create run
- prepare run
- worker renders current step
- current step executes and returns a structured result
- worker emits generic runtime events
- run reaches `WAITING`, `SUCCEEDED`, `FAILED`, or continues to the next step

Related docs:
- [`../skills/skill-schema.md`](../skills/skill-schema.md)
- [`../events/context-model.md`](../events/context-model.md)
- [`../events/runtime-events.md`](../events/runtime-events.md)
- [`../db/schema.md`](../db/schema.md)
