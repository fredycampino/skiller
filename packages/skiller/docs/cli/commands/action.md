# `skiller action`

Updates persisted runtime action state and writes JSON to `stdout`.

Runtime actions are emitted by `notify` steps with an `action` object. The
notify output does not store mutable action status. A successful done
transition is stored as an `ACTION_DONE` runtime event.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller action done <run_id> <step_id>` | Records a notify action as done. | Action update result. |

## Output Model

- `run_id`: run that owns the action.
- `step_id`: notify step that emitted the action.
- `status`: update status.
- `done`: whether the action is now done.
- `changed`: whether the command appended a new `ACTION_DONE` event.
- `error`: error message, present only when the action could not be marked done.

## Mark Done

Command:

```bash
skiller action done <run_id> <step_id>
```

Output when a new `ACTION_DONE` event is recorded:

```json
{
  "run_id": "run-uuid",
  "step_id": "auth_link",
  "status": "DONE",
  "done": true,
  "changed": true
}
```

Output when the action was already `done`:

```json
{
  "run_id": "run-uuid",
  "step_id": "auth_link",
  "status": "DONE",
  "done": true,
  "changed": false
}
```

Output when the step is not a notify action:

```json
{
  "run_id": "run-uuid",
  "step_id": "show_message",
  "status": "NOT_ACTION",
  "done": false,
  "changed": false,
  "error": "Step 'show_message' is not a notify action"
}
```

## Exit Code

- `0`: the action is `done`, including idempotent calls.
- `1`: the run or step was not found, or the step is not a notify action.
