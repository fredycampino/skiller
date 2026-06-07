# `skiller action`

Updates persisted runtime action state and writes JSON to `stdout`.

Runtime actions are emitted by `notify` steps with an `action` object. The
notify output does not store mutable action status. A successful done
transition is stored as an `ACTION_DONE` runtime event.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller action done <run_id> <action_uid>` | Records a notify action as done. | Action update result. |

## Output Model

- `run_id`: run that owns the action.
- `action_uid`: runtime-generated action identifier.
- `step_id`: notify step that emitted the action, present after the action is resolved.
- `status`: update status.
- `done`: whether the action is now done.
- `changed`: whether the command appended a new `ACTION_DONE` event.
- `error`: error message, present only when the action could not be marked done.

## Mark Done

Command:

```bash
skiller action done <run_id> <action_uid>
```

Output when a new `ACTION_DONE` event is recorded:

```json
{
  "run_id": "run-uuid",
  "action_uid": "action-uuid",
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
  "action_uid": "action-uuid",
  "step_id": "auth_link",
  "status": "DONE",
  "done": true,
  "changed": false
}
```

Output when the action does not exist:

```json
{
  "run_id": "run-uuid",
  "action_uid": "missing-action",
  "status": "ACTION_NOT_FOUND",
  "done": false,
  "changed": false,
  "error": "Action 'missing-action' not found in run 'run-uuid'"
}
```

## Exit Code

- `0`: the action is `done`, including idempotent calls.
- `1`: the run or action was not found.
