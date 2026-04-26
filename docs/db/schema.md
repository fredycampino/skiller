# DB Schema

Current SQLite schema used by Skiller.

Source of truth:
- [`sqlite_state_store.py`](../../src/skiller/infrastructure/db/sqlite_state_store.py)
- [`sqlite_execution_output_store.py`](../../src/skiller/infrastructure/db/sqlite_execution_output_store.py)
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

`step_executions_json` stores the functional state of the steps already executed by the run. In the
current model, this is the run's execution context for templates and later steps.

It is a JSON object indexed by `step_id`:

```json
{
  "ask_user": {
    "step_type": "wait_input",
    "input": {
      "prompt": "Message"
    },
    "evaluation": {
      "input_event_id": "external-event-id"
    },
    "output": {
      "text": "Input received.",
      "value": {
        "prompt": "Message",
        "payload": {
          "text": "hello"
        }
      },
      "body_ref": null
    }
  },
  "answer": {
    "step_type": "llm_prompt",
    "input": {
      "system": "You are a support assistant.",
      "prompt": "hello",
      "large_result": false
    },
    "evaluation": {
      "model": "fake-llm"
    },
    "output": {
      "text": "reply",
      "value": {
        "data": {
          "reply": "reply"
        }
      },
      "body_ref": null
    }
  }
}
```

Templates read this data through `output_value(...)`:

```text
{{output_value("ask_user").payload.text}}
{{output_value("answer").data.reply}}
```

Because the object is indexed by `step_id`, a loop that executes the same `step_id` more than once
keeps only the latest execution for that step id.

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
+-------------+------+-----------------------------------------------+
| column      | type | notes                                         |
+-------------+------+-----------------------------------------------+
| id          | TEXT | PK                                            |
| run_id      | TEXT | NOT NULL, FK -> runs(id)                      |
| step_id     | TEXT | NOT NULL                                      |
| wait_type   | TEXT | NOT NULL                                      |
| source_type | TEXT | NOT NULL (`input`/`webhook`/`channel`)        |
| source_name | TEXT | NOT NULL (`manual`, webhook name, channel)    |
| match_type  | TEXT | NOT NULL (`run`/`signal`/`channel_key`)       |
| match_key   | TEXT | NOT NULL (run id, signal key, channel key)    |
| status      | TEXT | NOT NULL                                      |
| created_at  | TEXT | NOT NULL, default CURRENT_TIMESTAMP           |
| expires_at  | TEXT | nullable                                      |
| resolved_at | TEXT | nullable                                      |
+-------------+------+-----------------------------------------------+
```

`wait_type` values:
- `wait_channel`
- `wait_input`
- `wait_webhook`

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

`output_body_json` stores the full output body for a step whose public output was reduced in
`runs.step_executions_json`. The step output keeps a durable pointer in `output.body_ref`:

```json
{
  "text": "Europe is one of the smallest continents...",
  "text_ref": "data.reply",
  "value": {
    "data": {
      "reply": "Europe is one of the smallest continents...",
      "reply_length": 980,
      "truncated": true
    }
  },
  "body_ref": "execution_output:abc123"
}
```

The `body_ref` prefix is stripped and matched against `execution_outputs.id`:

```text
runs.step_executions_json.<step_id>.output.body_ref = "execution_output:abc123"
execution_outputs.id = "abc123"
```

For `llm_prompt` with `large_result: true`, `output_body_json` stores the full effective
`output.value`:

```json
{
  "value": {
    "data": {
      "reply": "full long text..."
    }
  }
}
```

When a template calls `output_value("answer")` and the step output has a `body_ref`, the renderer
loads `execution_outputs.output_body_json` and resolves fields against its `value` instead of the
truncated `runs.step_executions_json` value.

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

## Run Deletion

`skiller delete <run_id>` deletes the run row and the database rows tied to that run in one
SQLite transaction:

- `execution_outputs` where `run_id` matches
- `external_receipts` whose `dedup_key` belongs to an `external_events` row tied to the run
- `external_events` where `run_id` or `consumed_by_run_id` matches
- `waits` where `run_id` matches
- `events` where `run_id` matches
- `runs` where `id` matches

`webhook_registrations` are global channel configuration and are not deleted by run cleanup.
