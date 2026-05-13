# Revive An Agent Run Manually

Use this only for development and debugging.

This procedure is for a run that:
- already failed,
- should be moved back to `ask_user`,
- and should become visible again as a real `wait_input` run.

This guide assumes an agent definition that loops back to `ask_user`.

It is not a logical resume of the failed step. It is a manual state repair.

## When To Use It

Use it when all of these are true:
- the run ended in `FAILED`,
- you want to continue the same conversation,
- the agent normally loops back to `ask_user`,
- and you accept that the old failure events remain in history.

Do not use it when:
- the run should continue inside the failed `agent` step,
- the agent does not route back to `ask_user`,
- or you need a clean historical event stream.

## What Must Be Updated

To revive the run in a way that works for event-driven consumers, update all three layers:

1. `runs`
- set `status = WAITING`
- set `current = ask_user`
- clear `finished_at`
- clear `cancel_reason`

2. `waits`
- insert a new `ACTIVE` row for:
  - `step_id = ask_user`
  - `wait_type = wait_input`
  - `source_type = input`
  - `source_name = manual`
  - `match_type = run`
  - `match_key = <run_id>`

3. `log_events`
- append:
  - `STEP_STARTED` for `ask_user`
  - `RUN_WAITING` for `ask_user`

If you only update `runs` and `waits`, the database state is revived, but clients that follow the event stream may still treat the run as dead because the latest historical event is still `RUN_FINISHED`.

## SQL Example

Replace `<run_id>` with the real run id.

```sql
BEGIN;

UPDATE runs
SET
  status = 'WAITING',
  current = 'ask_user',
  finished_at = NULL,
  cancel_reason = NULL,
  updated_at = CURRENT_TIMESTAMP
WHERE id = '<run_id>';

INSERT INTO waits (
  id,
  run_id,
  step_id,
  wait_type,
  source_type,
  source_name,
  match_type,
  match_key,
  status
) VALUES (
  lower(hex(randomblob(16))),
  '<run_id>',
  'ask_user',
  'wait_input',
  'input',
  'manual',
  'run',
  '<run_id>',
  'ACTIVE'
);

INSERT INTO log_events (
  id,
  run_id,
  sequence,
  event_type,
  step_id,
  step_type,
  agent_sequence,
  body_json
)
VALUES (
  lower(hex(randomblob(16))),
  '<run_id>',
  (SELECT COALESCE(MAX(sequence), 0) + 1 FROM log_events WHERE run_id = '<run_id>'),
  'STEP_STARTED',
  'ask_user',
  'wait_input',
  NULL,
  json_object()
);

INSERT INTO log_events (
  id,
  run_id,
  sequence,
  event_type,
  step_id,
  step_type,
  agent_sequence,
  body_json
)
VALUES (
  lower(hex(randomblob(16))),
  '<run_id>',
  (SELECT COALESCE(MAX(sequence), 0) + 1 FROM log_events WHERE run_id = '<run_id>'),
  'RUN_WAITING',
  'ask_user',
  'wait_input',
  NULL,
  json_object(
    'output',
    json_object(
      'text', 'Write a message. Type exit, quit, or bye to stop.',
      'value',
      json_object(
        'prompt', 'Write a message. Type exit, quit, or bye to stop.',
        'payload', NULL
      ),
      'body_ref', NULL
    )
  )
);

COMMIT;
```

## Verification

Check all three:

```sql
SELECT id, status, current, finished_at
FROM runs
WHERE id = '<run_id>';
```

Expected:
- `status = WAITING`
- `current = ask_user`
- `finished_at = NULL`

```sql
SELECT step_id, wait_type, status
FROM waits
WHERE run_id = '<run_id>'
ORDER BY rowid DESC
LIMIT 1;
```

Expected:
- `ask_user`
- `wait_input`
- `ACTIVE`

```sql
SELECT event_type, step_id, step_type, body_json, created_at
FROM log_events
WHERE run_id = '<run_id>'
ORDER BY sequence DESC
LIMIT 2;
```

Expected last events:
- `STEP_STARTED`
- `RUN_WAITING`

## Important Limitation

This does not erase the original failure.

The old log events remain:
- `STEP_ERROR`
- `RUN_FINISHED`

You are appending a new waiting tail after them. That is enough for development and for consumers that use latest state plus latest events, but it is not a full historical rewrite.
