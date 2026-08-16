# `skiller input`

Delivers human input to waiting runs and writes JSON to `stdout`.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller input receive <run_id> --text "..."` | Delivers text input to a waiting run. | Delivery result and resumed run ids. |
| `skiller input receive <run_id> --text "..." --wait` | Delivers text input and waits for the resumed run to reach another wait or a terminal status. | Delivery result and wait results. |

## Output Model

- `accepted`: whether the input was accepted.
- `run_id`: run targeted by the input.
- `matched_runs`: runs matched by the input event.
- `resumed_runs`: matched runs for which a worker resume was dispatched.

## Receive Text

Command:

```bash
skiller input receive <run_id> --text "database timeout"
```

Output:

```json
{
  "accepted": true,
  "run_id": "run-uuid",
  "matched_runs": ["run-uuid"],
  "resumed_runs": ["run-uuid"]
}
```

After accepting input, the CLI dispatches a worker resume for each matched run.

Add `--wait` when the caller must remain attached to the resumed run. The command
then waits until the run reaches `WAITING`, `SUCCEEDED`, `FAILED`, or `CANCELLED`.

## Exit Code

- `0`: the input was accepted and any matched runs were dispatched for resume.
- `1`: the input was rejected or a worker resume could not be started.
