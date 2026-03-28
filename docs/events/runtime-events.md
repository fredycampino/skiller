# Runtime Events

This document defines the proposed runtime event contract for the UI transcript.
It focuses on a small, stable set of generic events and a consistent `result` shape by `step_type`.

## Event Model

Every runtime event should follow this shape:

```json
{
  "id": "f2d2f7ef-5d58-4e2a-a7dd-48a4bb0d3f18",
  "type": "EVENT_NAME",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:15Z",
  "payload": {}
}
```

Rules:
- `id` uniquely identifies the event.
- `type` identifies the event contract.
- `run_id` identifies the run instance.
- `created_at` records when the event was created.
- `payload` contains the event-specific data.
- Event ordering is defined by the event store order.
- The UI transcript should consume structured events, not pre-rendered text.

## Generic Events

### RUN_CREATE
Emitted when a run is created from `/run`.

```json
{
  "id": "f2d2f7ef-5d58-4e2a-a7dd-48a4bb0d3f18",
  "type": "RUN_CREATE",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:15Z",
  "payload": {
    "skill": "chat"
  }
}
```

### RUN_RESUME
Emitted when a run resumes after input, webhook, or manual resume.

```json
{
  "id": "941f46b8-b93c-4d2a-b0d1-8f0d0d077758",
  "type": "RUN_RESUME",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:20Z",
  "payload": {
    "source": "manual"
  }
}
```

### STEP_STARTED
Emitted immediately before a step starts execution.

```json
{
  "id": "7aa84fd8-3f15-4afd-8772-a7fa9aa35d2d",
  "type": "STEP_STARTED",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:20Z",
  "payload": {
    "step": "answer",
    "step_type": "llm_prompt"
  }
}
```

### STEP_SUCCESS
Emitted when a step completes successfully.

```json
{
  "id": "0dd94e10-0aa7-4dc3-b57e-57c3a2f9f36d",
  "type": "STEP_SUCCESS",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:21Z",
  "payload": {
    "step": "answer",
    "step_type": "llm_prompt",
    "result": {
      "text": "Pablito clavó un clavito, ¿qué clavito clavó Pablito?"
    },
    "next": "show_reply"
  }
}
```

### STEP_ERROR
Emitted when a step fails.

```json
{
  "id": "76741831-baa6-4d92-85dd-a7b890482446",
  "type": "STEP_ERROR",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:21Z",
  "payload": {
    "step": "answer",
    "step_type": "llm_prompt",
    "error": "MiniMax request failed: <urlopen error [Errno -3] Temporary failure in name resolution>"
  }
}
```

### RUN_WAITING
Emitted when a run reaches a waiting state.

```json
{
  "id": "fdbb62da-0386-4208-a054-c3abf7d0f61b",
  "type": "RUN_WAITING",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:22Z",
  "payload": {
    "step": "start",
    "step_type": "wait_input",
    "result": {
      "prompt": "Write a message. Type exit, quit, or bye to stop."
    }
  }
}
```

### RUN_FINISHED
Emitted when a run reaches a terminal state.

Succeeded:

```json
{
  "id": "b177ef07-ad48-4148-8d47-d3cf69fe8f2d",
  "type": "RUN_FINISHED",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:23Z",
  "payload": {
    "status": "SUCCEEDED"
  }
}
```

Failed:

```json
{
  "id": "5700b5a1-a89b-4497-befc-bbc929d02279",
  "type": "RUN_FINISHED",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "created_at": "2026-03-28T10:30:23Z",
  "payload": {
    "status": "FAILED",
    "error": "MiniMax request failed: <urlopen error [Errno -3] Temporary failure in name resolution>"
  }
}
```

## Result By Step Type

The `result` field in `STEP_SUCCESS` and `RUN_WAITING` should be shaped according to `step_type`.

### wait_input

```json
{
  "prompt": "Write a message. Type exit, quit, or bye to stop."
}
```

### wait_webhook

```json
{
  "webhook": "github-pr-merged",
  "key": "42"
}
```

### switch

```json
{
  "next": "answer"
}
```

### when

```json
{
  "next": "done"
}
```

### llm_prompt

```json
{
  "text": "Pablito clavó un clavito, ¿qué clavito clavó Pablito?"
}
```

Optional structured output:

```json
{
  "text": "Pablito clavó un clavito, ¿qué clavito clavó Pablito?",
  "json": {
    "reply": "Pablito clavó un clavito, ¿qué clavito clavó Pablito?"
  }
}
```

Rules:
- `result.text` is required for `llm_prompt`.
- `result.json` is optional.
- The UI transcript should render `result.text`.

### notify

```json
{
  "message": "Chat closed."
}
```

### assign

```json
{
  "value": "computed result"
}
```

### mcp

```json
{
  "ok": true,
  "text": "Tool completed successfully."
}
```

```json
{
  "ok": false,
  "text": "MCP tool failed.",
  "error": "MCP tool failed."
}
```

Rules:
- `result.text` should summarize the MCP execution for the transcript.
- `result.ok` indicates whether the execution succeeded.
- `result.error` is optional and should be present when `ok` is `false`.

## Design Notes

- Generic events should be the source of truth for execution observers.
- Step-specific legacy events may still exist for debugging, but consumers should not depend on them as the primary contract.
- The event contract should be emitted centrally by the runtime orchestration layer whenever possible.
