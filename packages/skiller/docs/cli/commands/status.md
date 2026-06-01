# `skiller status`

Reads the current persisted runtime status of one run and writes a small JSON
summary to `stdout`.

## Command

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller status <run_id>` | Reads one run status by id. | Immediately after reading the database. |

`status` does not watch the run and does not stream events. Use `skiller logs`
for the event transcript and step-level details.

## Output Model

The command always returns the same public shape when the run exists:

- `run_id`: run id.
- `status`: current persisted run status.
- `wait_type`: active wait type, or `none`.
- `prompt`: input prompt for `wait_input`; otherwise an empty string.
- `last_event_sequence`: latest persisted runtime event cursor, or `null` when no event exists.
- `last_event_type`: latest persisted runtime event type, or an empty string when no event exists.

`status` does not include the full run model. It does not expose:

- `source`
- `ref`
- `current`
- `context`
- `created_at`
- `updated_at`
- webhook/channel correlation details such as `webhook`, `channel`, or `key`

Use `skiller logs <run_id>` when those details are needed.

## Running Run

Command:

```bash
skiller status <run_id>
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "RUNNING",
  "wait_type": "none",
  "prompt": "",
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
  "run_id": "run-uuid",
  "status": "WAITING",
  "wait_type": "input",
  "prompt": "Continue?",
  "last_event_sequence": 43,
  "last_event_type": "RUN_WAITING"
}
```

The current step id and step type are available in the corresponding
`RUN_WAITING` event:

```bash
skiller logs <run_id> --after 42 --limit 1
```

```json
[
  {
    "sequence": 43,
    "type": "RUN_WAITING",
    "step_id": "ask_user",
    "step_type": "wait_input"
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
  "run_id": "run-uuid",
  "status": "WAITING",
  "wait_type": "webhook",
  "prompt": "",
  "last_event_sequence": 44,
  "last_event_type": "RUN_WAITING"
}
```

Webhook name and key are available in the `RUN_WAITING` event payload:

```bash
skiller logs <run_id> --after 43 --limit 1
```

## Finished Run

Command:

```bash
skiller status <run_id>
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED",
  "wait_type": "none",
  "prompt": "",
  "last_event_sequence": 50,
  "last_event_type": "RUN_FINISHED"
}
```

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
