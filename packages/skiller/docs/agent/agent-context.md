# Agent Context

## Goal

Agent context is the append-only memory used by an `agent` step while it talks to the
LLM and executes tools.

Runtime step outputs still live in `runs.step_executions_json`. Agent context is separate because
one agent step can produce many messages, tool calls, and tool results under the same `step_id`.

## Logical Model

```python
AgentContextEntry(
    id: str,
    run_id: str,
    context_id: str,
    sequence: int,
    entry_type: str,
    payload: AgentContextPayload,
    usage: LLMUsage | None,
    source_step_id: str,
    created_at: str,
    message_type: str | None,
    window_start_sequence: int | None,
    delta_tokens: int | None,
    window_base: bool | None,
)
```

Fields:

- `id`: unique entry id.
- `run_id`: run that owns this context entry.
- `context_id`: logical agent memory id inside the run.
- `sequence`: monotonic order within `context_id`.
- `entry_type`: `user_message`, `assistant_message`, `tool_call`, or `tool_result`.
- `payload`: typed entry content used to rebuild the next LLM prompt.
- `usage`: optional provider usage for measured assistant responses.
- `source_step_id`: `agent` step that created the entry.
- `message_type`: assistant message subtype when `entry_type = assistant_message`.
- `window_start_sequence`: window start used by the measured request.
- `delta_tokens`: prompt-token delta attributed to the measured response.
- `window_base`: whether the measured response starts a new token-delta series.

## Table

```text
+-----------------------+---------+--------------------------------------+
| column                | type    | notes                                |
+-----------------------+---------+--------------------------------------+
| id                    | TEXT    | PK                                   |
| run_id                | TEXT    | NOT NULL, FK -> runs(id)             |
| context_id            | TEXT    | NOT NULL                             |
| sequence              | INTEGER | NOT NULL, ordered per context        |
| entry_type            | TEXT    | NOT NULL                             |
| message_type          | TEXT    | nullable, assistant subtype          |
| window_start_sequence | INTEGER | nullable                             |
| delta_tokens          | INTEGER | nullable                             |
| window_base           | INTEGER | nullable boolean                     |
| payload_json          | TEXT    | NOT NULL                             |
| usage_json            | TEXT    | nullable                             |
| source_step_id        | TEXT    | NOT NULL                             |
| created_at            | TEXT    | NOT NULL, default CURRENT_TIMESTAMP  |
+-----------------------+---------+--------------------------------------+
```

Indexes:

```text
idx_agent_context_entries_context(context_id, sequence)
```

## Window State

The live context-window marker is stored in `runs.agents_json` per agent:

```json
{
  "support_agent": {
    "agent_id": "support_agent",
    "context_id": "ctx-1",
    "window_start_sequence": 3,
    "window_base": true
  }
}
```

The context manager selects the next window by summing `delta_tokens` backwards until the
configured window width would be exceeded. It then updates the run agent window state.

When the next measured assistant response is persisted, the context publisher reads the run
agent window state and computes:

- `delta_tokens = prompt_tokens` when the response starts a new series.
- `delta_tokens = current_prompt_tokens - previous_prompt_tokens` inside the same series.

If provider usage is missing, `delta_tokens = 0`.

## Stats

`skiller agent stats <run_id> --agent <agent_id>` reports context diagnostics.

The stats are calculated from persisted deltas:

- `context.entries`: number of entries for the context.
- `context.estimated_tokens`: `SUM(delta_tokens)` across the context.
- `context.window.start_sequence`: latest measured `window_start_sequence`.
- `context.window.end_sequence`: latest entry sequence.
- `context.window.current_tokens`: `SUM(delta_tokens)` from `start_sequence`.

The command does not rebuild the full prompt and does not parse every payload.
