# `skiller resume`

Dispatches a worker to resume a waiting run and writes JSON to `stdout`.

`resume` is the user-facing command for continuing a run after external input
has been delivered. It starts the worker asynchronously and returns after the
worker process is dispatched.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller resume <run_id>` | Dispatches a worker to resume a waiting run. | After the worker process is started. |

## Output Model

- `run_id`: id of the run requested for resume.
- `resume_status`: dispatch status for the resume request.
- `worker_pid`: PID of the worker process started to resume the run.

## Resume Run

Command:

```bash
skiller resume <run_id>
```

Output:

```json
{
  "run_id": "run-uuid",
  "resume_status": "DISPATCHED",
  "worker_pid": 12345
}
```

`resume` does not wait for the run to finish. Use `skiller status <run_id>` and
`skiller logs <run_id>` to observe the resumed run.

## Exit Code

- `0`: the worker process was dispatched.
- `1`: the worker process could not be started.
