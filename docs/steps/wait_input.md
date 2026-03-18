# `wait_input`

## Status

Active functional design and base implementation.

## Goal

`wait_input` pauses a run until a human provides text through the CLI.

It should:
- leave the run in `WAITING`
- persist a durable wait
- resume the flow when input is received for the waiting run

## Minimal Shape

```yaml
- id: start
  type: wait_input
  prompt: "Write a short summary"
  next: done
```

## Rendering

`wait_input` follows the current runtime pattern:

- `RenderCurrentStepUseCase` renders the full step
- `prompt` is renderable

Supported placeholders:
- `{{inputs...}}`
- `{{results...}}`

## Waiting Semantics

When the step runs:

1. if no persisted input exists for that `run_id + current_step`:
- the run moves to `WAITING`
- an entry in `input_waits` is created or reused
- `current` stays on the same step
- the step is not consumed yet

2. if the input already exists:
- the step resolves
- the result is written to `context.results[step_id]`
- if `next` exists, the run moves `current` to that step
- if `next` does not exist, the run completes

## Result

When the step resolves, the expected result looks like:

```yaml
results.start.ok
results.start.prompt
results.start.payload.text
```

Example:

```json
{
  "ok": true,
  "prompt": "Write a short summary",
  "payload": {
    "text": "database timeout"
  }
}
```

## Input Reception

The current minimal system entrypoint is:

```bash
skiller input receive <run_id> --text "database timeout"
```

The received input must:
- be persisted first
- and only then attempt to resume the run

## Resume Flow

The expected flow is:

1. the run reaches `wait_input`
2. the input event is persisted
3. `HandleInputUseCase` confirms that the current step is `wait_input`
4. `ResumeRunUseCase` makes the run resumable
5. the runtime re-enters the loop
6. `ExecuteWaitInputStepUseCase` finds the persisted input and resolves the step
