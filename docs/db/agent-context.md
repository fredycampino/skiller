# Agent Context

## Status

Draft design. Runtime support is not implemented yet.

## Goal

Persist agent memory as append-only entries.

`runs.step_executions_json` stores one observable output per `step_id`. It is not suitable for
agent memory because one `agent` step can produce multiple turns under the same `step_id`.

## Logical Model

```python
AgentContextEntry(
    id: str,
    run_id: str,
    context_id: str,
    sequence: int,
    entry_type: str,
    payload: dict,
    source_step_id: str,
    idempotency_key: str,
    created_at: str,
)
```

Fields:

- `id`: unique entry id.
- `run_id`: run that owns this context entry.
- `context_id`: logical agent memory id inside the run.
- `sequence`: monotonic order within `run_id + context_id`.
- `entry_type`: one of the supported entry types.
- `payload`: full entry content used to rebuild the agent prompt. It may be large.
- `source_step_id`: `agent` step that created the entry.
- `idempotency_key`: stable key used to avoid duplicate appends.
- `created_at`: entry creation timestamp.

Entry types:

- `user_message`
- `assistant_message`
- `tool_call`
- `tool_result`

## Table

```text
+-----------------+---------+--------------------------------------+
| column          | type    | notes                                |
+-----------------+---------+--------------------------------------+
| id              | TEXT    | PK                                   |
| run_id          | TEXT    | NOT NULL, FK -> runs(id)             |
| context_id      | TEXT    | NOT NULL                             |
| sequence        | INTEGER | NOT NULL                             |
| entry_type      | TEXT    | NOT NULL                             |
| payload_json    | TEXT    | NOT NULL, full payload               |
| source_step_id  | TEXT    | NOT NULL                             |
| idempotency_key | TEXT    | NOT NULL                             |
| created_at      | TEXT    | NOT NULL, default CURRENT_TIMESTAMP  |
+-----------------+---------+--------------------------------------+
```

Indexes:

```text
idx_agent_context_entries_context(run_id, context_id, sequence)
idx_agent_context_entries_idempotency(run_id, context_id, idempotency_key)
```

`idx_agent_context_entries_idempotency` should be unique.

## Entry Payloads

User message:

```json
{
  "type": "user_message",
  "text": "Check the latest build failure."
}
```

Assistant final message:

```json
{
  "type": "assistant_message",
  "turn_id": "turn-2",
  "text": "The failing test is test_example.py::test_build."
}
```

Tool call:

```json
{
  "type": "tool_call",
  "turn_id": "turn-1",
  "tool": "shell",
  "args": {
    "command": "pytest -q"
  }
}
```

Tool result:

```json
{
  "type": "tool_result",
  "turn_id": "turn-1",
  "tool": "shell",
  "data": {
    "ok": false,
    "exit_code": 1,
    "stderr": "..."
  }
}
```

## Example Context

An `agent` loop reconstructs `AgentContext` from ordered entries:

```json
{
  "run_id": "run-1",
  "context_id": "thread-1",
  "entries": [
    {
      "id": "entry-1",
      "sequence": 1,
      "entry_type": "user_message",
      "payload": {
        "type": "user_message",
        "text": "Check why the tests are failing."
      },
      "source_step_id": "support_agent",
      "idempotency_key": "user:input-1",
      "created_at": "2026-04-22T21:40:00Z"
    },
    {
      "id": "entry-2",
      "sequence": 2,
      "entry_type": "tool_call",
      "payload": {
        "type": "tool_call",
        "turn_id": "turn-1",
        "tool": "shell",
        "args": {
          "command": "pytest -q"
        }
      },
      "source_step_id": "support_agent",
      "idempotency_key": "tool_call:turn-1",
      "created_at": "2026-04-22T21:40:05Z"
    },
    {
      "id": "entry-3",
      "sequence": 3,
      "entry_type": "tool_result",
      "payload": {
        "type": "tool_result",
        "turn_id": "turn-1",
        "tool": "shell",
        "data": {
          "ok": false,
          "exit_code": 1,
          "stderr": "ModuleNotFoundError: No module named 'requests'"
        }
      },
      "source_step_id": "support_agent",
      "idempotency_key": "tool_result:turn-1",
      "created_at": "2026-04-22T21:40:08Z"
    },
    {
      "id": "entry-4",
      "sequence": 4,
      "entry_type": "assistant_message",
      "payload": {
        "type": "assistant_message",
        "turn_id": "turn-2",
        "text": "The tests fail because `requests` is missing."
      },
      "source_step_id": "support_agent",
      "idempotency_key": "final:turn-2",
      "created_at": "2026-04-22T21:40:15Z"
    }
  ]
}
```

This example has one user task, one tool turn, and one final assistant turn.

## Idempotency

Agent context appends must be idempotent.

Suggested keys:

```text
user:<input_event_id>
tool_call:<turn_id>
tool_result:<turn_id>
final:<turn_id>
```

The uniqueness boundary is:

```text
run_id + context_id + idempotency_key
```

This prevents duplicate entries if a worker appends context and then crashes before the run state is
advanced.

Keep `id` separate from `idempotency_key`: `id` stays a stable row UUID for references and debug,
while `idempotency_key` can change format and remains unique only within `run_id + context_id`.

## Read Model

Load context entries by `run_id + context_id`, ordered by `sequence`.

For prompt construction, the `agent` step can load the most recent entries:

```sql
SELECT *
FROM agent_context_entries
WHERE run_id = ? AND context_id = ?
ORDER BY sequence DESC
LIMIT ?
```

Then reverse the result in memory before sending it to the LLM.

## Relationship To Existing Tables

- `runs.step_executions_json` stores the final observable output of the `agent` step.
- `agent_context_entries` stores the internal append-only memory used by the agent loop.
- `agent_context_entries.payload_json` is the source of truth for each memory entry and may be
  large.
- `events` remains an observability stream, not the functional source of truth.
