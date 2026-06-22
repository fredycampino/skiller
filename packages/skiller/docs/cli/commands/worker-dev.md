# `skiller worker`

Runs low-level worker operations.

This command is for development and operator debugging. Normal usage should go
through `skiller run`, `skiller resume`, `skiller input receive`,
`skiller webhook receive`, or `skiller channel receive`; those commands dispatch
workers as needed.

## Commands

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller worker start <run_id>` | Prepares a `CREATED` run and launches a worker process. | Worker start result. |
| `skiller worker run <run_id>` | Executes a prepared run in the current process. | Run result. |
| `skiller worker resume <run_id>` | Resumes a `WAITING` run in the current process. | Resume result. |

## `start`

Command:

```bash
skiller worker start <run_id>
```

Behavior:

- requires the run to be `CREATED`
- prepares the run by resolving its start step
- starts `skiller worker run <run_id>` in a child process when preparation succeeds

Output:

```json
{
  "run_id": "run-uuid",
  "start_status": "PREPARED",
  "status": "RUNNING",
  "worker_pid": 12345
}
```

## `run`

Command:

```bash
skiller worker run <run_id>
```

Behavior:

- requires the run to be prepared
- executes steps until the run reaches a terminal or waiting state

Output:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED"
}
```

## `resume`

Command:

```bash
skiller worker resume <run_id>
```

Behavior:

- attempts to resume a waiting run
- executes steps until the run reaches a terminal or waiting state

Output:

```json
{
  "run_id": "run-uuid",
  "resume_status": "RESUMED",
  "status": "SUCCEEDED"
}
```

## Exit Code

- `0`: the worker operation succeeded.
- `1`: the run was in the wrong state, missing, failed, or could not be resumed.
