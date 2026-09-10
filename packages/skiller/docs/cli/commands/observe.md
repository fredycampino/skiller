# `skiller observe`

Streams persisted runtime events for one run as JSON Lines (JSONL). It begins
with a bounded history and remains connected until the run is terminal.

```bash
skiller observe <run_id> [--after <sequence>] [--tail <count>]
```

`stdout` contains only JSONL frames. Diagnostics and errors are written to
`stderr`.

## Cursor and initial history

`--after N` declares that the consumer has already processed sequence `N`; the
stream contains only events with `sequence > N`. `N` must be non-negative and
cannot be greater than the last persisted sequence when observation starts.

`--tail N` bounds only the initial history. Its default is `100` and its
maximum is `1000`. The initial cursor is the greater of `--after` (or `0`) and
`last_sequence - --tail`. Events persisted after the command starts are not
bounded by `--tail`.

The first frame records the effective cursor:

```json
{"kind":"start","version":1,"run_id":"run-uuid","requested_after":null,"effective_after":42,"last_sequence":142,"tail":100,"truncated":true}
```

`truncated` is true when events older than `effective_after` were omitted by
the initial history bound.

## Frames

Each persisted runtime event is emitted unchanged inside an `event` frame:

```json
{"kind":"event","event":{"sequence":43,"id":"event-uuid","run_id":"run-uuid","type":"RUN_WAITING","step_id":"ask_user","step_type":"wait_input","agent_sequence":null,"created_at":"2026-05-12T10:30:15Z","payload":{}}}
```

When the last persisted event represents an active `wait_input` or
`wait_webhook`, the stream also emits one control frame for that event:

```json
{"kind":"wait","sequence":43,"wait_type":"input","prompt":"Continue?"}
{"kind":"wait","sequence":44,"wait_type":"webhook"}
```

The command does not emit a `wait` frame for `wait_channel`. A waiting run does
not close the stream.

After all events have been drained and the persisted terminal event has been
observed, the final frame is:

```json
{"kind":"stop","sequence":91,"status":"succeeded"}
```

`status` is one of `succeeded`, `failed`, or `cancelled`. `stop` is emitted
only after `RUN_FINISHED`; a terminal run status alone does not end the stream.

## Lifecycle and exit status

The observer continues while a run is `RUNNING` or `WAITING`, including long
waits. It terminates normally after the terminal `stop` frame, or cleanly when
it receives `SIGINT` or `SIGTERM` (or its output pipe closes). A clean stop by
signal or closed pipe does not guarantee a `stop` frame.

- `0`: the stream ended normally or was cancelled cleanly.
- Non-zero: invalid arguments, an unknown run, or a runtime/query error.
