# `skiller run`

Runs a runnable and writes JSON to `stdout`.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller run <runnable>` | Runs an internal catalog runnable. | When the run finishes or reaches a stable state. |
| `skiller run --file ./runnable.yaml` | Runs a runnable from a file. | When the run finishes or reaches a stable state. |
| `skiller run <runnable> --arg key=value` | Runs with explicit inputs. | When the run finishes or reaches a stable state. |
| `skiller run <runnable> --detach` | Starts the worker without watching the run. | After the worker is started. |
| `skiller run <runnable> --logs` | Runs and includes raw events in the output. | When the run finishes or reaches a stable state. |

Stable states observed by `run` without `--detach`:

- `WAITING`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`
- `TIMEOUT`
- `INTERRUPTED`

## Output Model

- `run_id`: id of the created run.
- `status`: run status observed when `run` returns.
- `worker_pid`: PID of the worker process started for the run.
- `current`: current step, usually present when the run is `WAITING`.
- `wait_type`: active wait type, for example `input`.
- `prompt`: text to show the user when waiting for input.
- `logs`: raw runtime event list, present only with `--logs`.

## Internal Catalog Runnable

Command:

```bash
skiller run <runnable>
```

Internal runnable ids resolve from `packages/skiller/agents/<id>/agent.yaml`.

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
  "worker_pid": 12345
}
```

## File Runnable

Command:

```bash
skiller run --file ./runnable.yaml
```

Output:

```json
{
  "run_id": "run-uuid",
  "status": "SUCCEEDED",
  "worker_pid": 12345
}
```

## Arguments

Command:

```bash
skiller run <runnable> --arg owner=my-org --arg repo=my-repo
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
skiller run <runnable> --detach
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
skiller run <runnable> --logs
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
        "skill": "runnable-id",
        "skill_source": "internal"
      }
    }
  ]
}
```

`logs` contains raw runtime events. It is not the rendered transcript.

## Exit Code

- `0`: the command ran and the final observed status is not `FAILED`.
- `1`: creating the run, starting the worker, watching the run, or the final observed status failed.
