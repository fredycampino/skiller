# `skiller status`

Reads the current persisted state of a run and writes JSON to `stdout`.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller status <run_id>` | Reads one run by id without runtime context. | Immediately after reading the database. |
| `skiller status <run_id> --context` | Reads one run by id including runtime context. | Immediately after reading the database. |

`status` does not watch the run and does not stream events.

## Output Model

- `id`: run id.
- `skill_source`: source used to create the run, for example `internal` or `file`.
- `skill_ref`: flow reference used to create the run.
- `status`: current persisted run status.
- `current`: current step id, or `null` when no current step is active.
- `context`: persisted runtime context for the run, present only with `--context`.
- `created_at`: run creation timestamp.
- `updated_at`: last run update timestamp.
- `last_event_sequence`: latest persisted runtime event cursor, when events exist.
- `last_event_type`: latest persisted runtime event type, when events exist.
- `wait_type`: active wait type. Present only when `status` is `WAITING` and
  the current step is `wait_input`, `wait_webhook`, or `wait_channel` with
  resolvable wait metadata.
- `prompt`: input prompt, present for input waits.
- `webhook`: webhook name, present for webhook waits.
- `key`: webhook correlation key, present for webhook waits.

`status` does not include `step_type`. Read the latest event with `logs` when
the current step type is needed.

## Running Run

Command:

```bash
skiller status <run_id>
```

Output:

```json
{
  "id": "run-uuid",
  "source": "internal",
  "ref": "ci",
  "status": "RUNNING",
  "current": "support_agent",
  "created_at": "2026-05-12T10:30:10Z",
  "updated_at": "2026-05-12T10:30:12Z",
  "last_event_sequence": 42,
  "last_event_type": "AGENT_TOOL_CALL"
}
```

## Waiting For Input

Command:

```bash
skiller status <run_id>
```

Output:

```json
{
  "id": "run-uuid",
  "skill_source": "internal",
  "skill_ref": "chat",
  "status": "WAITING",
  "current": "ask_user",
  "created_at": "2026-05-12T10:30:10Z",
  "updated_at": "2026-05-12T10:30:15Z",
  "wait_type": "input",
  "prompt": "Continue?",
  "last_event_sequence": 43,
  "last_event_type": "RUN_WAITING"
}
```

The current step type is available in the corresponding `RUN_WAITING` event:

```bash
skiller logs <run_id> --after 42 --limit 1
```

```json
[
  {
    "sequence": 43,
    "type": "RUN_WAITING",
    "payload": {
      "step": "ask_user",
      "step_type": "wait_input"
    }
  }
]
```

## Waiting For Webhook

Command:

```bash
skiller status <run_id>
```

Output:

```json
{
  "id": "run-uuid",
  "skill_source": "internal",
  "skill_ref": "webhook_signal_oracle",
  "status": "WAITING",
  "current": "wait_signal",
  "created_at": "2026-05-12T10:30:10Z",
  "updated_at": "2026-05-12T10:30:15Z",
  "wait_type": "webhook",
  "webhook": "market-signal",
  "key": "btc-usd",
  "last_event_sequence": 44,
  "last_event_type": "RUN_WAITING"
}
```

## Finished Run

Command:

```bash
skiller status <run_id>
```

Output:

```json
{
  "id": "run-uuid",
  "skill_source": "internal",
  "skill_ref": "ci",
  "status": "SUCCEEDED",
  "current": null,
  "created_at": "2026-05-12T10:30:10Z",
  "updated_at": "2026-05-12T10:31:00Z",
  "last_event_sequence": 50,
  "last_event_type": "RUN_FINISHED"
}
```

## Include Runtime Context

Command:

```bash
skiller status <run_id> --context
```

Output:

```json
{
  "id": "run-uuid",
  "skill_source": "internal",
  "skill_ref": "ci",
  "status": "WAITING",
  "current": "ask_user",
  "context": {
    "inputs": {},
    "step_executions": {}
  },
  "created_at": "2026-05-12T10:30:10Z",
  "updated_at": "2026-05-12T10:30:15Z",
  "prompt": "Continue?",
  "last_event_sequence": 43,
  "last_event_type": "RUN_WAITING"
}
```

`context` can be large. Use `--context` only when debugging runtime data.

## Missing Run

Command:

```bash
skiller status <run_id>
```

Output:

```text
Run not found
```

## Exit Code

- `0`: the run exists and status JSON was printed.
- `1`: the run does not exist.
