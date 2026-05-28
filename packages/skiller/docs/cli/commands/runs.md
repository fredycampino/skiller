# `skiller runs`

Lists recent runs and writes JSON to `stdout`.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller runs` | Lists recent runs with the default limit. | JSON array of runs. |
| `skiller runs --limit 50` | Lists a bounded number of recent runs. | JSON array capped by `--limit`. |
| `skiller runs --status WAITING` | Lists runs matching one status. | JSON array filtered by status. |
| `skiller runs --status WAITING --status FAILED` | Lists runs matching any provided status. | JSON array filtered by status. |

## Output Model

The command always returns a JSON array.

Common fields:

- `id`: run id.
- `status`: current run status.
- `skill_ref`: flow reference used to create the run.
- `current`: current step, usually present when the run is waiting.
- `updated_at`: last update timestamp.

Additional fields may be present depending on the run state and query store.

## Recent Runs

Command:

```bash
skiller runs
```

Output:

```json
[
  {
    "id": "run-uuid",
    "status": "WAITING",
    "skill_ref": "support_agent",
    "current": "ask_user",
    "updated_at": "2026-05-12 10:30:15"
  }
]
```

## Limit

Command:

```bash
skiller runs --limit 50
```

`--limit` caps the number of runs returned. The default is `20`.

## Status Filter

Command:

```bash
skiller runs --status WAITING --status FAILED
```

`--status` can be repeated. Values are normalized to uppercase before querying.

## Exit Code

- `0`: runs were read and JSON was printed.
