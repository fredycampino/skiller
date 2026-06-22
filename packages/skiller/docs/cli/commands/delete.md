# `skiller delete`

Deletes one run and its run-owned database rows.

This is a destructive operator command. It writes JSON to `stdout`.

## Command

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller delete <run_id>` | Deletes one run and associated rows. | Deletion result. |

## Output Model

- `run_id`: target run id.
- `status`: delete status.
- `deleted`: whether the run was deleted.
- `error`: failure reason, present when `deleted` is false.

Status values:

- `DELETED`: the run existed and was deleted.
- `RUN_NOT_FOUND`: no persisted run exists for `run_id`.
- `INVALID_RUN_ID`: `run_id` was empty after trimming.

## Delete Run

Command:

```bash
skiller delete <run_id>
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "DELETED",
  "deleted": true
}
```

Missing run:

```json
{
  "run_id": "missing-run",
  "status": "RUN_NOT_FOUND",
  "deleted": false,
  "error": "Run 'missing-run' not found"
}
```

## Deleted Data

The command removes:

- run row
- runtime events
- waits
- external events tied to the run
- deduplication receipts linked to those external events
- agent context entries for the run

Webhook registrations are global configuration and are not deleted.

## Exit Code

- `0`: the run was deleted.
- `1`: the run id was invalid or the run was not found.
