# `skiller logs`

Reads persisted runtime events for a run and writes raw JSON to `stdout`.

`logs` is not the rendered transcript. It returns the event stream as stored by
the runtime.

For the full event envelope and event type examples, see
[`../../events/event.md`](../../events/event.md).

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller logs <run_id>` | Reads all persisted events for a run. | JSON array of events. |
| `skiller logs <run_id> --after <sequence>` | Reads events after a cursor. | JSON array of events with `sequence > <sequence>`. |
| `skiller logs <run_id> --after <sequence> --limit 100` | Reads a bounded page after a cursor. | JSON array capped by `--limit`. |

## Output Model

The command always returns a JSON array.

- `sequence`: monotonic event cursor assigned by the runtime database.
- `id`: event id.
- `run_id`: run that owns the event.
- `type`: event type.
- `step_id`: related step id, when the event belongs to a step.
- `step_type`: related step type, when the event belongs to a step.
- `agent_sequence`: matching agent context sequence for agent context events.
- `created_at`: event creation timestamp.
- `payload`: event-specific data.

## All Events

Command:

```bash
skiller logs <run_id>
```

Output:

```json
[
  {
    "sequence": 1,
    "id": "event-uuid",
    "run_id": "run-uuid",
    "type": "RUN_CREATE",
    "step_id": null,
    "step_type": null,
    "agent_sequence": null,
    "created_at": "2026-05-12T10:30:10Z",
    "payload": {
      "skill": "runnable-id",
      "skill_source": "internal"
    }
  },
  {
    "sequence": 2,
    "id": "event-uuid",
    "run_id": "run-uuid",
    "type": "STEP_STARTED",
    "step_id": "support_agent",
    "step_type": "agent",
    "agent_sequence": null,
    "created_at": "2026-05-12T10:30:11Z",
    "payload": {}
  }
]
```

## Events After Cursor

Command:

```bash
skiller logs <run_id> --after 42
```

Output:

```json
[
  {
    "sequence": 43,
    "id": "event-uuid",
    "run_id": "run-uuid",
    "type": "RUN_WAITING",
    "step_id": "ask_user",
    "step_type": "wait_input",
    "agent_sequence": null,
    "created_at": "2026-05-12T10:30:15Z",
    "payload": {
      "output": {
        "text": "Continue?",
        "value": {
          "prompt": "Continue?",
          "payload": null
        },
        "body_ref": null
      }
    }
  }
]
```

`--after N` returns events with `sequence > N`.

## Bounded Page

Command:

```bash
skiller logs <run_id> --after 42 --limit 100
```

Output:

```json
[
  {
    "sequence": 43,
    "id": "event-uuid",
    "run_id": "run-uuid",
    "type": "RUN_WAITING",
    "step_id": "ask_user",
    "step_type": "wait_input",
    "agent_sequence": null,
    "created_at": "2026-05-12T10:30:15Z",
    "payload": {}
  }
]
```

`--limit` caps the number of returned events.

## Incremental Polling

Use `status.last_event_sequence` as the latest known cursor:

```bash
skiller status <run_id>
skiller logs <run_id> --after <last_seen_sequence> --limit 100
```

Consumers should keep their own `last_seen_sequence` and update it with the
highest `sequence` they processed.

## Exit Code

- `0`: events were read and JSON was printed.
