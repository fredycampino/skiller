# `skiller agent`

Controls a running agent and reads persisted agent context diagnostics.

`skiller agent` commands write JSON to `stdout`.

## Combinations

| Command | Behavior | Returns |
| --- | --- | --- |
| `skiller agent interrupt <run_id>` | Enqueues an interrupt for the current agent turn. | Interrupt enqueue result. |
| `skiller agent stats <run_id> --agent <agent_id>` | Reads persisted context-window stats for one agent in a run. | Agent context stats. |
| `skiller agent models <run_id>` | Lists model options from the agent config effective for a run. | Provider/model rows. |

## `interrupt`

Command:

```bash
skiller agent interrupt <run_id>
```

Behavior:

- validates that the run exists
- enqueues a steering item with `type = "agent_interrupt"`
- does not cancel the run
- is consumed by the agent loop at a steering checkpoint

Output:

```json
{
  "run_id": "run-uuid",
  "status": "ENQUEUED",
  "enqueued": true,
  "item": {
    "type": "agent_interrupt"
  }
}
```

Failure output:

```json
{
  "run_id": "missing-run",
  "status": "RUN_NOT_FOUND",
  "enqueued": false,
  "error": "Run 'missing-run' not found"
}
```

Fields:

- `run_id`: target run id.
- `status`: enqueue status.
- `enqueued`: whether the interrupt was queued.
- `item`: queued steering item, present when `enqueued = true`.
- `error`: failure reason, present when `enqueued = false`.

Status values:

- `ENQUEUED`: interrupt was appended to the run steering queue.
- `INVALID_RUN_ID`: `run_id` was empty after trimming.
- `RUN_NOT_FOUND`: no persisted run exists for `run_id`.

## `stats`

Command:

```bash
skiller agent stats <run_id> --agent <agent_id>
```

Behavior:

- validates that the run exists
- validates that the agent exists in the run
- validates that the agent has an attached persisted context
- reads persisted context stats
- reads the agent config effective at command time to report context capacity

Output:

```json
{
  "run_id": "run-uuid",
  "agent_id": "mono",
  "status": "OK",
  "ok": true,
  "context_id": "ctx-uuid",
  "context": {
    "entries": 412,
    "estimated_tokens": 156802,
    "window": {
      "start_sequence": 274,
      "end_sequence": 412,
      "current_tokens": 73835,
      "limit_tokens": 80000,
      "capacity_tokens": 100000
    }
  }
}
```

Failure output:

```json
{
  "run_id": "run-uuid",
  "agent_id": "mono",
  "status": "AGENT_CONTEXT_NOT_READY",
  "ok": false,
  "error": "Agent 'mono' has no attached context in run 'run-uuid'"
}
```

Fields:

- `run_id`: target run id.
- `agent_id`: target agent id.
- `status`: stats lookup status.
- `ok`: whether stats were returned.
- `context_id`: persisted agent context id, present when `ok = true`.
- `context.entries`: total persisted context entries.
- `context.estimated_tokens`: estimated historical context size.
- `context.window.start_sequence`: first entry currently included in the context window.
- `context.window.end_sequence`: latest entry currently included in the context window.
- `context.window.current_tokens`: tokens reported for the latest measured context window.
- `context.window.limit_tokens`: threshold used to move `start_sequence`.
- `context.window.capacity_tokens`: configured provider or agent context capacity before the
  compaction ratio is applied.
- `error`: failure reason, present when `ok = false`.

Status values:

- `OK`: stats were returned.
- `RUN_NOT_FOUND`: no persisted run exists for `run_id`.
- `AGENT_NOT_FOUND`: no persisted agent exists for `agent_id` in the run.
- `AGENT_CONTEXT_NOT_READY`: the agent exists but has no attached context yet.

## `models`

Command:

```bash
skiller agent models <run_id>
```

Behavior:

- validates that the run exists
- reads the agent config effective for that run
- returns provider/model rows only for public providers (`codex`, `minimax`, `bedrock`)
- reports each provider config source as `global`, `local`, `env`, or `none`
- omits internal test providers such as `null` and `fake`
- does not include credentials, credential paths, profiles, timeouts, or token metadata

Output:

```json
{
  "run_id": "run-uuid",
  "status": "OK",
  "ok": true,
  "providers": [
    {
      "name": "codex",
      "source": "global",
      "models": [
        {
          "name": "gpt-5.5",
          "active": true
        },
        {
          "name": "gpt-5.4",
          "active": false
        }
      ]
    }
  ]
}
```

Failure output:

```json
{
  "run_id": "missing-run",
  "status": "RUN_NOT_FOUND",
  "ok": false,
  "error": "Run 'missing-run' not found"
}
```

Fields:

- `run_id`: target run id.
- `status`: model lookup status.
- `ok`: whether models were returned.
- `providers[].name`: provider name.
- `providers[].source`: provider config source: `global`, `local`, `env`, or `none`.
- `providers[].models[].name`: supported model name.
- `providers[].models[].active`: whether the model is the default provider's configured model.
- `error`: failure reason, present when `ok = false`.

Status values:

- `OK`: models were returned.
- `RUN_NOT_FOUND`: no persisted run exists for `run_id`.

## Exit Code

- `0`: command succeeded.
- `1`: command failed or the requested run/agent/context was not found.
