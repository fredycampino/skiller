# DB Schema

Current SQLite schema used by Skiller.

Source of truth:
- [`sqlite_state_store.py`](../../src/skiller/infrastructure/db/sqlite_state_store.py)
- [`sqlite_webhook_registry.py`](../../src/skiller/infrastructure/db/sqlite_webhook_registry.py)
- [`bootstrap_runtime.py`](../../src/skiller/application/use_cases/bootstrap_runtime.py)

## `runs`

Represents:
- the persisted runtime state of a run
- source of truth for `inputs`, `step_executions`, current step, and lifecycle status

```text
+------------------------+----------+--------------------------------------+
| column                 | type     | notes                                |
+------------------------+----------+--------------------------------------+
| id                     | TEXT     | PK                                   |
| skill_source           | TEXT     | NOT NULL                             |
| skill_ref              | TEXT     | NOT NULL                             |
| skill_snapshot_json    | TEXT     | NOT NULL                             |
| status                 | TEXT     | NOT NULL                             |
| current                | TEXT     | nullable                             |
| inputs_json            | TEXT     | NOT NULL, default '{}'               |
| step_executions_json   | TEXT     | NOT NULL, default '{}'               |
| steering_messages_json | TEXT     | NOT NULL, default '[]'               |
| cancel_reason          | TEXT     | nullable                             |
| created_at             | TEXT     | NOT NULL, default CURRENT_TIMESTAMP  |
| updated_at             | TEXT     | NOT NULL, default CURRENT_TIMESTAMP  |
| finished_at            | TEXT     | nullable                             |
+------------------------+----------+--------------------------------------+
```

Indexes:

```text
idx_runs_status_updated_at(status, updated_at)
```

## `waits`

Represents:
- active or resolved waits owned by a run step
- one unified model for `wait_channel`, `wait_input`, and `wait_webhook`
- normalized matching around `source_*` and `match_*`

```text
+------------------+-------+---------------------------------------------------+
| column           | type  | notes                                             |
+------------------+-------+---------------------------------------------------+
| id               | TEXT  | PK                                                |
| run_id           | TEXT  | NOT NULL, FK -> runs(id)                          |
| step_id          | TEXT  | NOT NULL                                          |
| wait_type        | TEXT  | NOT NULL (`wait_channel`/`wait_input`/`wait_webhook`) |
| source_type      | TEXT  | NOT NULL (`input`/`webhook`/`channel`)            |
| source_name      | TEXT  | NOT NULL (`manual`, webhook name, channel name)   |
| match_type       | TEXT  | NOT NULL (`run`/`signal`/`channel_key`)           |
| match_key        | TEXT  | NOT NULL (run id, signal key, channel key)        |
| status           | TEXT  | NOT NULL                                          |
| created_at       | TEXT  | NOT NULL, default CURRENT_TIMESTAMP               |
| expires_at       | TEXT  | nullable                                          |
| resolved_at      | TEXT  | nullable                                          |
+------------------+-------+---------------------------------------------------+
```

Indexes:

```text
idx_waits_run_step_type_status(run_id, step_id, wait_type, status)
idx_waits_source_match_type_status(source_type, source_name, match_type, match_key, wait_type, status)
```

## `events`

Represents:
- the generic runtime event stream
- observability for `/logs`, `watch`, and the TUI transcript

```text
+--------------+-------+--------------------------------------+
| column       | type  | notes                                |
+--------------+-------+--------------------------------------+
| id           | TEXT  | PK                                   |
| run_id       | TEXT  | nullable                             |
| type         | TEXT  | NOT NULL                             |
| payload_json | TEXT  | NOT NULL                             |
| created_at   | TEXT  | NOT NULL, default CURRENT_TIMESTAMP  |
+--------------+-------+--------------------------------------+
```

Indexes:

```text
idx_events_run_created_at(run_id, created_at)
```

## `execution_outputs`

Represents:
- full output bodies stored for steps with `large_result: true`
- durable payloads addressed by `output.body_ref`

```text
+------------------+-------+--------------------------------------+
| column           | type  | notes                                |
+------------------+-------+--------------------------------------+
| id               | TEXT  | PK                                   |
| run_id           | TEXT  | NOT NULL                             |
| step_id          | TEXT  | NOT NULL                             |
| output_body_json | TEXT  | NOT NULL                             |
| created_at       | TEXT  | NOT NULL, default CURRENT_TIMESTAMP  |
+------------------+-------+--------------------------------------+
```

Indexes:

```text
idx_execution_outputs_run_step_created_at(run_id, step_id, created_at)
```

## `external_receipts`

Represents:
- accepted external deliveries used only for deduplication
- idempotency guard before creating a new `external_event`

```text
+--------------+-------+---------------------------------------------------+
| column       | type  | notes                                             |
+--------------+-------+---------------------------------------------------+
| dedup_key    | TEXT  | PK                                                |
| source_type  | TEXT  | NOT NULL                                          |
| source_name  | TEXT  | NOT NULL                                          |
| match_type   | TEXT  | NOT NULL                                          |
| match_key    | TEXT  | NOT NULL                                          |
| payload_json | TEXT  | NOT NULL                                          |
| created_at   | TEXT  | NOT NULL, default CURRENT_TIMESTAMP               |
+--------------+-------+---------------------------------------------------+
```

Indexes:

```text
idx_external_receipts_source_match_created_at(source_type, source_name, match_type, match_key, created_at)
```

## `external_events`

Represents:
- raw external payloads that may resume a waiting step
- normalized around `source_*` and `match_*`

```text
+------------------+-------+---------------------------------------------------+
| column           | type  | notes                                             |
+------------------+-------+---------------------------------------------------+
| id               | TEXT  | PK                                                |
| source_type      | TEXT  | NOT NULL (`input`/`webhook`/`channel`)            |
| source_name      | TEXT  | NOT NULL                                          |
| match_type       | TEXT  | NOT NULL (`run`/`signal`/`channel_key`)           |
| match_key        | TEXT  | NOT NULL                                          |
| run_id           | TEXT  | nullable, FK -> runs(id)                          |
| step_id          | TEXT  | nullable                                          |
| external_id      | TEXT  | nullable (message id, delivery id, etc.)          |
| dedup_key        | TEXT  | nullable                                          |
| status             | TEXT  | NOT NULL (`pending`/`consumed`)                 |
| consumed_by_run_id | TEXT  | nullable, FK -> runs(id)                        |
| consumed_at        | TEXT  | nullable                                        |
| payload_json     | TEXT  | NOT NULL                                          |
| created_at       | TEXT  | NOT NULL, default CURRENT_TIMESTAMP               |
+------------------+-------+---------------------------------------------------+
```

Indexes:

```text
idx_external_events_source_run_step_created_at(source_type, run_id, step_id, status, created_at)
idx_external_events_source_match_created_at(source_type, source_name, match_type, match_key, status, created_at)
```

## `webhook_registrations`

Represents:
- configured webhook channels and their shared secret
- registry data used by webhook registration/list/remove and HTTP validation

```text
+------------+---------+--------------------------------------+
| column     | type    | notes                                |
+------------+---------+--------------------------------------+
| webhook    | TEXT    | PK                                   |
| secret     | TEXT    | NOT NULL                             |
| enabled    | INTEGER | NOT NULL, default 1                  |
| created_at | TEXT    | NOT NULL, default CURRENT_TIMESTAMP  |
+------------+---------+--------------------------------------+
```

## Notes

- `runs.step_executions_json` is the source of truth for persisted step execution data.
- `events.payload_json` is the observability stream used by `/logs`, `watch`, and the UI transcript.
- `execution_outputs.output_body_json` stores the full output body behind `output.body_ref`.
- for `llm_prompt`, that body currently stores the full `value` used to rebuild the final text through `text_ref`.
- `waits` is the unified wait table for `wait_channel`, `wait_input`, and `wait_webhook`.
- `wait_type` remains the step-level discriminator for wait semantics.
- `source_*` models where an external event came from.
- `match_*` models how a wait or event is correlated.
- `external_events` is the unified storage for raw external payloads used to resume waits.
- `external_events.status` tracks whether an event is still pending or already consumed by a run.
- external-event lookup is scoped to `run.created_at`, not `wait.created_at`.
- matching is FIFO: oldest active wait, then oldest pending matching event.
- `webhook_registrations` is owned by `SqliteWebhookRegistry`, not by `SqliteStateStore`.
