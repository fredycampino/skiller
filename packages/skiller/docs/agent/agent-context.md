# Agent context database

This document describes the SQLite persistence model for agent contexts. The
publication and pruning algorithms are documented in:

- [`agent-context-prune.md`](agent-context-prune.md)
- [`agent-context-compaction.md`](agent-context-compaction.md)

## Persistence model

An agent context is append-only history associated with one run and one agent.
Entries are stored in `agent_context_entries`; the current compaction boundaries
are stored in `agent_context_state`. Compaction changes visibility in the next
LLM request and never deletes entry rows.

## `agent_context_entries`

```sql
CREATE TABLE agent_context_entries (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  context_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  entry_type TEXT NOT NULL,
  message_type TEXT NULL,
  delta_tokens INTEGER NULL,
  delta_compact_tokens INTEGER NULL,
  compaction_id INTEGER NULL,
  payload_json TEXT NOT NULL,
  usage_json TEXT NULL,
  source_step_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
```

### Columns

- `id`: unique row identifier.
- `run_id`: owning runtime run. It references `runs(id)`.
- `context_id`: logical agent-context identifier.
- `sequence`: append order within `context_id`.
- `entry_type`: `user_message`, `assistant_message`, `tool_call`, or `tool_result`.
- `message_type`: assistant subtype when applicable: `tool_calls` or `final`.
- `delta_tokens`: token growth represented by every assistant response. It is
  estimated when provider usage is absent or does not contain `prompt_tokens`.
- `delta_compact_tokens`: compacted representation weight for a visible entry.
  It is `NULL` for prunable entries.
- `compaction_id`: compaction generation of an assistant usage marker. It is
  `NULL` when the assistant response has no usable `prompt_tokens`; the initial
  generation is `0` and increases when compaction updates the context state.
- `payload_json`: serialized typed context payload. It is always present.
- `usage_json`: provider usage when available; otherwise `NULL`.
- `source_step_id`: agent step that produced the entry.
- `created_at`: persistence timestamp.

An assistant entry with `usage_json` containing `prompt_tokens` and a
`compaction_id` is a usage marker. Every assistant entry has `delta_tokens`,
including entries whose provider usage is unavailable. `compaction_id` is
diagnostic state shared by valid usage markers and the context generation;
marker calculation does not require a second window field.

## `agent_context_state`

```sql
CREATE TABLE agent_context_state (
  context_id TEXT PRIMARY KEY,
  start_sequence INTEGER NOT NULL,
  compacted_sequence INTEGER NULL,
  compaction_id INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK(start_sequence > 0),
  CHECK(compacted_sequence IS NULL OR compacted_sequence >= start_sequence - 1),
  CHECK(compaction_id >= 0)
);
```

### Columns

- `context_id`: context whose compaction state is stored.
- `start_sequence`: first sequence in the current logical window.
- `compacted_sequence`: last sequence in the compacted range, inclusive. It is
  `NULL` before the first compaction.
- `compaction_id`: generation number for marker accounting. It starts at `0`
  and increments once when a new compaction state is persisted.
- `updated_at`: last state-persistence timestamp.

The marker publisher reads this state. If the last comparable marker belongs
to the same `compaction_id` and has a non-decreasing `prompt_tokens` value, it
uses the prompt-token delta. Otherwise it estimates `delta_tokens` from
persisted context data. Publishing a marker does not mutate
`agent_context_state`.

There is no foreign key from `agent_context_state.context_id` to
`agent_context_entries.context_id`; the context identifier is coordinated by
the runtime and its associated run-agent record.

## Indexes

```sql
CREATE INDEX idx_agent_context_entries_context
  ON agent_context_entries(context_id, sequence);

CREATE INDEX idx_agent_context_usage_markers_context_sequence
  ON agent_context_entries(context_id, sequence)
  WHERE usage_json IS NOT NULL
    AND delta_tokens IS NOT NULL
    AND compaction_id IS NOT NULL;
```

The first index supports ordered context reads. The partial index supports
lookups of persisted usage markers.

## Relationships and deletion

- A run can own multiple agent contexts through its persisted agent records.
- A context contains entries from one agent across many turns.
- Run deletion removes its associated context entries explicitly. The foreign
  key does not declare `ON DELETE CASCADE`.
- Context entries are not deleted during compaction or pruning.
- `agent_context_state` is keyed by `context_id` and is not linked to run
  deletion by a foreign key.
