# Agent Events

This document defines the runtime event contract for agent internal observability.

Agent events are persisted in `log_events`, the same stream used by `logs`, CLI,
and TUI consumers. The full common event contract is defined in
[`../events/event.md`](../events/event.md).

## Event Envelope

Agent events use the standard runtime event envelope:

```json
{
  "sequence": 101,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_TOOL_RESULT",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 34,
  "created_at": "2026-05-12T10:30:17Z",
  "payload": {}
}
```

Rules:

- `sequence` is the runtime event sequence.
- `step_id` is the agent step id.
- `step_type` is always `agent`.
- `agent_sequence` is the matching `agent_context_entries.sequence` for events
  backed by an agent context entry.
- `payload` mirrors the matching agent context entry payload.
- `payload.parent_sequence` links a tool call or result to the assistant message
  that introduced the tool block, when that assistant message exists.

## Event Types

Current agent event types:

- `AGENT_ASSISTANT_MESSAGE`
- `AGENT_FINAL_ASSISTANT_MESSAGE`
- `AGENT_TOOL_CALL`
- `AGENT_TOOL_RESULT`
- `AGENT_INTERRUPTED`
- `AGENT_MAX_TURNS_EXHAUSTED`

## `AGENT_ASSISTANT_MESSAGE`

Emitted when the assistant returns visible content that introduces one or more
tool calls.

```json
{
  "sequence": 102,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_ASSISTANT_MESSAGE",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 33,
  "created_at": "2026-05-12T10:30:16Z",
  "payload": {
    "total_tokens": 1000,
    "text": "I will inspect the branch state before continuing."
  }
}
```

Rules:

- only tool-call assistant messages use this event type.
- `total_tokens` is the `usage.total_tokens` reported by the LLM for that request.
- truncation: `text` is truncated by the agent event output policy.
- not truncated: `total_tokens`.

## `AGENT_FINAL_ASSISTANT_MESSAGE`

Emitted when the agent finishes with a final assistant message.

```json
{
  "sequence": 103,
  "id": "event-uuid",
  "run_id": "run-123",
  "type": "AGENT_FINAL_ASSISTANT_MESSAGE",
  "step_id": "support_agent",
  "step_type": "agent",
  "agent_sequence": 34,
  "created_at": "2026-05-12T10:30:18Z",
  "payload": {
    "total_tokens": 2144,
    "text": "Done"
  }
}
```

Rules:

- `total_tokens` is the `usage.total_tokens` reported by the LLM for that request.
- truncation: `text` is truncated by the agent event output policy.
- not truncated: `total_tokens`.
- if the provider returns no visible content, this event is omitted.

## `AGENT_TOOL_CALL`

Emitted when the agent loop records one tool call.

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

Rules:

- one event is emitted per tool call.
- `tool_call_id` correlates the call with its result.
- truncation: string fields inside `args` can be truncated; arrays can be capped;
  JSON payload size can be capped by the agent event output policy.
- not truncated: `turn_id`, `parent_sequence`, `tool_call_id`, `tool`.
- `parent_sequence` is omitted for tool-only turns.

## `AGENT_TOOL_RESULT`

Emitted when a tool call produces a result.

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

Rules:

- `status`, `data`, `text`, and `error` use the same shape as the matching
  agent context `tool_result` entry.
- tool execution failures caused by the model or policy feedback can be
  persisted as tool results.
- programmer/runtime exceptions should fail the step/run instead of being
  converted into agent feedback.
- truncation: `text`, `error`, and string fields inside `data` can be truncated;
  arrays can be capped; JSON payload size can be capped by the agent event
  output policy.
- not truncated: `turn_id`, `parent_sequence`, `tool_call_id`, `tool`, `status`.

## `AGENT_INTERRUPTED`

Emitted when the agent step stops because the current turn was interrupted.

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

This event has no assistant text. Consumers should render an interruption state
instead of treating the empty final output as a normal blank answer.

## `AGENT_MAX_TURNS_EXHAUSTED`

Emitted when the agent step stops because it consumed the configured maximum
agent turns without producing a final answer.

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

Consumers should render this as a limit state. The step result carries the same
finish reason in its output data.

## Multi-Tool Turn Example

```json
[
  {
    "sequence": 201,
    "id": "event-uuid",
    "run_id": "run-123",
    "type": "AGENT_ASSISTANT_MESSAGE",
    "step_id": "support_agent",
    "step_type": "agent",
    "agent_sequence": 70,
    "created_at": "2026-05-12T10:31:00Z",
    "payload": {
      "total_tokens": 240,
      "text": "I will inspect the branch state and recent commits."
    }
  },
  {
    "sequence": 202,
    "id": "event-uuid",
    "run_id": "run-123",
    "type": "AGENT_TOOL_CALL",
    "step_id": "support_agent",
    "step_type": "agent",
    "agent_sequence": 71,
    "created_at": "2026-05-12T10:31:01Z",
    "payload": {
      "type": "tool_call",
      "turn_id": "turn-7",
      "parent_sequence": 70,
      "tool_call_id": "call-1",
      "tool": "shell",
      "args": {
        "command": "git status --short"
      }
    }
  },
  {
    "sequence": 203,
    "id": "event-uuid",
    "run_id": "run-123",
    "type": "AGENT_TOOL_RESULT",
    "step_id": "support_agent",
    "step_type": "agent",
    "agent_sequence": 72,
    "created_at": "2026-05-12T10:31:02Z",
    "payload": {
      "type": "tool_result",
      "turn_id": "turn-7",
      "parent_sequence": 70,
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
]
```

## Redaction and Truncation

Agent event payloads must be safe to show in logs and UI:

- redact sensitive keys in `args` and `data`.
- redact common secret token text patterns in free text.
- truncate assistant text and tool result text before persistence.
- cap large JSON values before persistence.
