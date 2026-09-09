# `skiller run`

Runs a flow and writes JSON to `stdout`.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller run <reference>` | Runs a flow resolved from the effective flow paths. | When the run finishes or reaches a stable state. |
| `skiller run <reference> --arg key=value` | Runs with explicit inputs. | When the run finishes or reaches a stable state. |
| `skiller run <reference> --detach` | Starts the worker without watching the run. | After the worker is started. |
| `skiller run <reference> --logs` | Runs and includes raw events in the output. | When the run finishes or reaches a stable state. |

Stable states observed by `run` without `--detach`:

- `WAITING`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`

## Output Model

- `run_id`: id of the created run.
- `status`: run status observed when `run` returns.
- `worker_pid`: PID of the worker process started for the run.
- `current`: current step, usually present when the run is `WAITING`.
- `wait_type`: active wait type, for example `input`.
- `prompt`: text to show the user when waiting for input.
- `logs`: raw runtime event list, present only with `--logs`.

## Flow References

Command:

```bash
skiller run @flows
skiller run @reportes/diario
skiller run ~/flows/reportes/diario
skiller run ./flows/reportes/diario.yaml
```

References beginning with `@` are searched first in the packaged `apps/agents` directory, then in the runtime current working directory, and finally in configured `flow_paths`. The first matching file is used. A simple reference tries `<root>/<reference>.yaml` first and then `<root>/<reference>/<reference>.yaml`. A hierarchical reference tries `<root>/<reference>.yaml` first and then `<root>/<reference>/<last-segment>.yaml`.

References beginning with `~` are resolved from the user's home directory. Relative and absolute paths are used directly, with `.yaml` added when no supported extension is provided. The flow definition and any files referenced by it must remain available while the run executes.

Output when the run succeeds:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED",
  "worker_pid": 12345
}
```

Output when the run waits for input:

```json
{
  "run_id": "run-uuid",
  "status": "WAITING",
  "current": "ask_user",
  "wait_type": "input",
  "prompt": "Continue?",
  "worker_pid": 12345
}
```

Output when the run fails:

```json
{
  "run_id": "run-uuid",
  "status": "FAILED",
  "worker_pid": 12345,
  "error": {
    "code": "RUN_EXECUTION_FAILED",
    "message": "Step 'send_message' requires channel"
  }
}
```

## Direct Path

Pass a home, relative, or absolute path directly:

```bash
skiller run ./flow.yaml
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED",
  "worker_pid": 12345
}
```

The run keeps a persisted snapshot. If this external flow file disappears after the run is created, the run continues from that snapshot; files explicitly referenced by its steps must still be available.

## Arguments

Command:

```bash
skiller run <flow> --arg owner=my-org --arg repo=my-repo
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED",
  "worker_pid": 12345
}
```

## Detached Run

Command:

```bash
skiller run <flow> --detach
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "CREATED",
  "worker_pid": 12345
}
```

`--detach` returns after starting the worker. It does not wait for the run to
finish or wait for input.

## Include Logs

Command:

```bash
skiller run <flow> --logs
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED",
  "worker_pid": 12345,
  "logs": [
    {
      "sequence": 1,
      "id": "event-uuid",
      "run_id": "run-uuid",
      "type": "RUN_CREATE",
      "created_at": "2026-05-12T10:30:10Z",
      "payload": {
        "ref": "flow-id",
        "source": "internal"
      }
    }
  ]
}
```

`logs` contains raw runtime events. It is not the rendered transcript.

## Error Output

Errors handled by `run` are written as one JSON object to `stdout`. The error
contract contains only a stable `code` and an actionable `message`:

```json
{
  "error": {
    "code": "WEBHOOK_WAIT_CONFLICT",
    "message": "Webhook 'github:42' is already being waited by run 'existing-run'. Delete it with 'skiller delete existing-run' or wait for it to finish."
  }
}
```

When the run was created before the failure, its existing fields are preserved:

```json
{
  "run_id": "run-uuid",
  "status": "CREATED",
  "error": {
    "code": "WORKER_START_FAILED",
    "message": "worker unavailable"
  }
}
```

A failed execution reports `RUN_EXECUTION_FAILED` and preserves `run_id`,
`status`, and `worker_pid`. A missing flow reports `FLOW_NOT_FOUND`; a runtime
startup failure reports `RUNTIME_INITIALIZATION_FAILED`. Invalid run target or
`--arg` values report `RUN_ARGUMENT_INVALID`. Watch progress remains on `stderr`
and is not mixed with the final JSON document.

## Exit Code

- `0`: the command ran and the final observed status is not `FAILED`.
- `1`: creating the run, starting the worker, watching the run, or the final observed status failed.
