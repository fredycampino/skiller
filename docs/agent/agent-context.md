# Agent Context

## Status

Implemented.

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
  "message_type": "final",
  "text": "The failing test is test_example.py::test_build."
}
```

Assistant message that introduces tool calls:

```json
{
  "type": "assistant_message",
  "turn_id": "turn-1",
  "message_type": "tool_calls",
  "text": "I will inspect the failing command output before answering."
}
```

Tool call:

```json
{
  "type": "tool_call",
  "turn_id": "turn-1",
  "parent_sequence": 2,
  "tool_call_id": "call-1",
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
  "parent_sequence": 2,
  "tool_call_id": "call-1",
  "tool": "shell",
  "status": "COMPLETED",
  "data": {
    "ok": false,
    "exit_code": 1,
    "stderr": "..."
  },
  "text": "",
  "error": null
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
      "idempotency_key": "user:support_agent:turn-1",
      "created_at": "2026-04-22T21:40:00Z"
    },
    {
      "id": "entry-2",
      "sequence": 2,
      "entry_type": "assistant_message",
      "payload": {
        "type": "assistant_message",
        "turn_id": "turn-1",
        "message_type": "tool_calls",
        "text": "I will inspect the test output before answering."
      },
      "source_step_id": "support_agent",
      "idempotency_key": "assistant:support_agent:turn-1",
      "created_at": "2026-04-22T21:40:03Z"
    },
    {
      "id": "entry-3",
      "sequence": 3,
      "entry_type": "tool_call",
      "payload": {
        "type": "tool_call",
        "turn_id": "turn-1",
        "parent_sequence": 2,
        "tool_call_id": "call-1",
        "tool": "shell",
        "args": {
          "command": "pytest -q"
        }
      },
      "source_step_id": "support_agent",
      "idempotency_key": "tool_call:support_agent:turn-1:call-1",
      "created_at": "2026-04-22T21:40:05Z"
    },
    {
      "id": "entry-4",
      "sequence": 4,
      "entry_type": "tool_result",
      "payload": {
        "type": "tool_result",
        "turn_id": "turn-1",
        "parent_sequence": 2,
        "tool_call_id": "call-1",
        "tool": "shell",
        "status": "COMPLETED",
        "data": {
          "ok": false,
          "exit_code": 1,
          "stderr": "ModuleNotFoundError: No module named 'requests'"
        },
        "text": "",
        "error": null
      },
      "source_step_id": "support_agent",
      "idempotency_key": "tool_result:support_agent:turn-1:call-1",
      "created_at": "2026-04-22T21:40:08Z"
    },
    {
      "id": "entry-5",
      "sequence": 5,
      "entry_type": "assistant_message",
      "payload": {
        "type": "assistant_message",
        "turn_id": "turn-2",
        "message_type": "final",
        "text": "The tests fail because `requests` is missing."
      },
      "source_step_id": "support_agent",
      "idempotency_key": "assistant:support_agent:turn-2",
      "created_at": "2026-04-22T21:40:15Z"
    }
  ]
}
```

This example has one user task, one tool call inside `turn-1`, and one final assistant turn.

`turn_id` groups entries that belong to the same assistant response.
`tool_call_id` identifies one concrete tool call inside that turn.
`message_type` distinguishes assistant content that introduces tool calls from final assistant content.
`parent_sequence` links `tool_call` and `tool_result` entries back to the assistant message of the same turn.

That allows one assistant turn to persist:

- one assistant content block
- multiple `tool_call` entries
- multiple `tool_result` entries

## Idempotency

Agent context appends must be idempotent.

Suggested keys:

```text
user:<source_step_id>:<turn_id>
tool_call:<source_step_id>:<turn_id>:<tool_call_id>
tool_result:<source_step_id>:<turn_id>:<tool_call_id>
assistant:<source_step_id>:<turn_id>
```

The uniqueness boundary is:

```text
run_id + context_id + idempotency_key
```

This prevents duplicate entries if a worker appends context and then crashes before the run state is
advanced.

Keep `id` separate from `idempotency_key`: `id` stays a stable row UUID for references and debug,
while `idempotency_key` can change format and remains unique only within `run_id + context_id`.

## Multi-Tool Turns

The current context model supports more than one tool call in the same assistant turn.

The persistence shape is:

- one shared `turn_id` for the whole assistant turn
- one distinct `tool_call_id` per native tool call
- one `tool_result` matched to the same `tool_call_id`

Prompt reconstruction uses:

- `assistant(..., tool_calls=[...])` for all tool calls of the turn
- one `tool(...)` message per persisted tool result

This keeps the next LLM request aligned with the original provider response order.

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
