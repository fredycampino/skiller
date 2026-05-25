# Event

This document defines the common event envelope currently used by Skiller
persisted events.

Runtime events and agent events share the same persisted shape. Agent events are
runtime events with agent-specific payloads.

## Event Envelope

Every persisted event has this shape:

```json
{
  "sequence": 4083,
  "id": "f2d2f7ef-5d58-4e2a-a7dd-48a4bb0d3f18",
  "run_id": "e367bf20-7457-4c44-a4be-e48796025e1c0",
  "type": "EVENT_NAME",
  "step_id": null,
  "step_type": null,
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:15Z",
  "payload": {}
}
```

Current data model:

```python
@dataclass(frozen=True)
class RuntimeEvent:
    sequence: int
    id: str
    run_id: str
    type: RuntimeEventType
    step_id: str | None
    step_type: str | None
    agent_sequence: int | None
    created_at: str
    payload: RuntimeEventPayload
```

Draft model before persistence:

```python
@dataclass(frozen=True)
class RuntimeEventDraft:
    run_id: str
    type: RuntimeEventType
    payload: RuntimeEventPayload
    step_id: str | None = None
    step_type: str | None = None
    agent_sequence: int | None = None
```

Payload model:

```python
RuntimeEventPayload: TypeAlias = (
    RunCreatedPayload
    | RunResumedPayload
    | RunWaitingPayload
    | RunFinishedPayload
    | StepStartedPayload
    | StepSuccessPayload
    | StepErrorPayload
    | ActionDonePayload
    | AgentEventPayload
    | AgentLifecyclePayload
    | InputReceivedPayload
)
```

Event type model:

```python
class RuntimeEventType(StrEnum):
    RUN_CREATE = "RUN_CREATE"
    RUN_RESUME = "RUN_RESUME"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCESS = "STEP_SUCCESS"
    STEP_ERROR = "STEP_ERROR"
    RUN_WAITING = "RUN_WAITING"
    RUN_FINISHED = "RUN_FINISHED"
    ACTION_DONE = "ACTION_DONE"
    AGENT_ASSISTANT_MESSAGE = "AGENT_ASSISTANT_MESSAGE"
    AGENT_FINAL_ASSISTANT_MESSAGE = "AGENT_FINAL_ASSISTANT_MESSAGE"
    AGENT_TOOL_CALL = "AGENT_TOOL_CALL"
    AGENT_TOOL_RESULT = "AGENT_TOOL_RESULT"
    AGENT_INTERRUPTED = "AGENT_INTERRUPTED"
    AGENT_MAX_TURNS_EXHAUSTED = "AGENT_MAX_TURNS_EXHAUSTED"
    INPUT_RECEIVED = "INPUT_RECEIVED"
```

Fields:

- `sequence`: monotonic event cursor assigned by the runtime database.
- `id`: unique event id.
- `run_id`: run instance that owns the event.
- `type`: event contract name.
- `step_id`: related step id, when the event belongs to a step.
- `step_type`: related step type, when the event belongs to a step.
- `agent_sequence`: matching agent context sequence for agent context events.
- `created_at`: event creation timestamp.
- `payload`: event-specific data.

## Reading Logs

`logs` returns persisted events as raw JSON, not the rendered transcript.

```bash
skiller status <run_id>
skiller logs <run_id> --after <last_event_sequence> --limit 100
```

- `status.last_event_sequence` is the latest persisted event cursor.
- `--after N` returns events with `sequence > N`.
- omit `--after` to read all events for the run.

## Runtime Events

Runtime events describe run and step lifecycle transitions.

### `RUN_CREATE`

```json
{
  "sequence": 100,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "RUN_CREATE",
  "step_id": null,
  "step_type": null,
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:10Z",
  "payload": {
    "skill": "chat",
    "skill_source": "internal"
  }
}
```

### `RUN_RESUME`

```json
{
  "sequence": 101,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "RUN_RESUME",
  "step_id": null,
  "step_type": null,
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:11Z",
  "payload": {
    "source": "manual"
  }
}
```

### `STEP_STARTED`

```json
{
  "sequence": 102,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "STEP_STARTED",
  "step_id": "answer",
  "step_type": "agent",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:12Z",
  "payload": {}
}
```

### `STEP_SUCCESS`

```json
{
  "sequence": 103,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "STEP_SUCCESS",
  "step_id": "answer",
  "step_type": "agent",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:15Z",
  "payload": {
    "output": {
      "text": "hello",
      "value": {
        "reply": "hello"
      },
      "body_ref": null
    },
    "next": "ask_user"
  }
}
```

`payload.next` is present when the successful step points to another step.

### `STEP_ERROR`

```json
{
  "sequence": 104,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "STEP_ERROR",
  "step_id": "answer",
  "step_type": "agent",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:16Z",
  "payload": {
    "error": "Agent step 'answer' failed"
  }
}
```

### `ACTION_DONE`

`ACTION_DONE` is emitted when `skiller action done <run_id> <step_id>` changes
a notify action from `pending` to `done`.

Idempotent calls for an already done action do not emit another event.

```json
{
  "sequence": 109,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "ACTION_DONE",
  "step_id": "auth_link",
  "step_type": "notify",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:21Z",
  "payload": {
    "action_type": "open_url",
    "status": "done"
  }
}
```

### `RUN_WAITING`

`RUN_WAITING` is emitted when the current step is a wait step.

```json
{
  "sequence": 105,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "RUN_WAITING",
  "step_id": "ask_user",
  "step_type": "wait_input",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:17Z",
  "payload": {
    "output": {
      "text": "Write a message.",
      "value": {
        "prompt": "Write a message.",
        "payload": null
      },
      "body_ref": null
    }
  }
}
```

### `RUN_FINISHED`

Succeeded:

```json
{
  "sequence": 106,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "RUN_FINISHED",
  "step_id": null,
  "step_type": null,
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:18Z",
  "payload": {
    "status": "SUCCEEDED"
  }
}
```

Failed:

```json
{
  "sequence": 107,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "RUN_FINISHED",
  "step_id": null,
  "step_type": null,
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:19Z",
  "payload": {
    "status": "FAILED",
    "error": "LLM step 'answer' returned invalid JSON"
  }
}
```

Current `RUN_FINISHED` statuses emitted by runtime are `SUCCEEDED` and `FAILED`.
`RUN_FINISHED` with `FAILED` can also be emitted during run preparation when the
start step cannot be resolved.

### `INPUT_RECEIVED`

`INPUT_RECEIVED` is emitted when manual input is accepted for a `wait_input`
step.

```json
{
  "sequence": 108,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "INPUT_RECEIVED",
  "step_id": "ask_user",
  "step_type": null,
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:20Z",
  "payload": {
    "payload": {
      "text": "continue"
    }
  }
}
```

## Agent Event Example

Agent events use the same envelope. `agent_sequence` points to the matching
agent context entry. `payload` mirrors the agent context payload.

```json
{
  "sequence": 101,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_TOOL_RESULT",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 32,
  "created_at": "2026-05-12T10:30:16Z",
  "payload": {
    "type": "tool_result",
    "turn_id": "turn-4",
    "parent_sequence": 30,
    "tool_call_id": "call_abc",
    "tool": "shell",
    "status": "COMPLETED",
    "data": {
      "ok": true,
      "exit_code": 0
    },
    "text": "ok",
    "error": null
  }
}
```

Rules:

- `sequence` always belongs to the persisted event stream.
- for agent events, `agent_sequence` belongs to the agent context.
- for agent events, `payload.parent_sequence` links a tool call or result
  to its parent agent context entry.
- `sequence` and `agent_sequence` are different counters.

## Agent Events

### `AGENT_ASSISTANT_MESSAGE`

Assistant message that introduces tool calls:

```json
{
  "sequence": 101,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_ASSISTANT_MESSAGE",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 32,
  "created_at": "2026-05-12T10:30:15Z",
  "payload": {
    "total_tokens": 1000,
    "text": "I will inspect the branch state before continuing."
  }
}
```

Truncation:

- `text` is truncated by the agent event output policy.
- `total_tokens` is not truncated.

### `AGENT_FINAL_ASSISTANT_MESSAGE`

```json
{
  "sequence": 102,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_FINAL_ASSISTANT_MESSAGE",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 33,
  "created_at": "2026-05-12T10:30:16Z",
  "payload": {
    "total_tokens": 2144,
    "text": "Done"
  }
}
```

Truncation:

- `text` is truncated by the agent event output policy.
- `total_tokens` is not truncated.

### `AGENT_TOOL_CALL`

```json
{
  "sequence": 102,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_TOOL_CALL",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 33,
  "created_at": "2026-05-12T10:30:16Z",
  "payload": {
    "type": "tool_call",
    "turn_id": "turn-1",
    "parent_sequence": 32,
    "tool_call_id": "call-1",
    "tool": "shell",
    "args": {
      "command": "git status --short"
    }
  }
}
```

`agent_sequence` is the persisted agent context entry sequence.

Truncation:

- string fields inside `args` can be truncated; arrays can be capped; JSON
  payload size can be capped by the agent event output policy.
- `turn_id`, `parent_sequence`, `tool_call_id`, and `tool` are not truncated.

### `AGENT_TOOL_RESULT`

```json
{
  "sequence": 103,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_TOOL_RESULT",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 34,
  "created_at": "2026-05-12T10:30:17Z",
  "payload": {
    "type": "tool_result",
    "turn_id": "turn-1",
    "parent_sequence": 32,
    "tool_call_id": "call-1",
    "tool": "shell",
    "status": "COMPLETED",
    "data": {
      "ok": true,
      "exit_code": 0,
      "stdout": "",
      "stderr": ""
    },
    "text": "Command completed successfully.",
    "error": null
  }
}
```

`payload` uses the same shape as the matching agent context tool result.

Truncation:

- `text`, `error`, and string fields inside `data` can be truncated; arrays can
  be capped; JSON payload size can be capped by the agent event output policy.
- `turn_id`, `parent_sequence`, `tool_call_id`, `tool`, and `status` are not
  truncated.

### `AGENT_INTERRUPTED`

```json
{
  "sequence": 104,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_INTERRUPTED",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:18Z",
  "payload": {
    "turn_id": "turn-1",
    "stop_reason": "interrupted"
  }
}
```

### `AGENT_MAX_TURNS_EXHAUSTED`

```json
{
  "sequence": 105,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_MAX_TURNS_EXHAUSTED",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": null,
  "created_at": "2026-05-12T10:30:19Z",
  "payload": {
    "turn_id": "turn-2",
    "stop_reason": "max_turns_exhausted"
  }
}
```
