# Agent Loop Events

This document defines the runtime event contract for agent internal tool-loop observability.

These events are appended to the same `events` stream used by `/logs`, `watch`, CLI, and TUI.

## Status

Current behavior:

- `AGENT_ASSISTANT_MESSAGE`
- `AGENT_TOOL_CALL`
- `AGENT_TOOL_RESULT`
- assistant turns can emit content, tool calls, or both
- `tool_call_id` is emitted on both events
- one assistant turn can emit more than one tool event pair

## Event Envelope

Each event uses the standard runtime event envelope from
[`../events/runtime-events.md`](../events/runtime-events.md):

```json
{
  "id": "evt-001",
  "type": "EVENT_NAME",
  "run_id": "bf1c9390-04f7-49c8-89dd-ccb6ad4a714c",
  "created_at": "2026-04-27T10:00:00Z",
  "payload": {}
}
```

Rules:

- `type` is one of `AGENT_ASSISTANT_MESSAGE`, `AGENT_TOOL_CALL`, or `AGENT_TOOL_RESULT`.
- `payload.step_type` is always `agent`.
- events are append-only and ordered by `created_at` + event id.
- `payload.turn_id` groups events from the same assistant response.
- `payload.tool_call_id` identifies one concrete native tool call inside that turn.
- `parent_sequence` is present only when the same turn emitted `AGENT_ASSISTANT_MESSAGE`.

## `AGENT_ASSISTANT_MESSAGE`

Emitted when the assistant returns visible content during an agent turn.

This includes:

- content that introduces one or more tool calls
- final assistant content with no tool calls

```json
{
  "id": "evt-000",
  "type": "AGENT_ASSISTANT_MESSAGE",
  "run_id": "bf1c9390-04f7-49c8-89dd-ccb6ad4a714c",
  "created_at": "2026-04-27T10:00:00Z",
  "payload": {
    "step": "support_agent",
    "step_type": "agent",
    "turn_id": "turn-1",
    "sequence": 32,
    "message_type": "tool_calls",
    "text": "I checked the branch state. Now I will create the squashed branch."
  }
}
```

Required payload fields:

- `step` (string)
- `step_type` (string, expected `agent`)
- `turn_id` (string)
- `sequence` (integer, sequence of the persisted `agent_context` entry)
- `message_type` (string, expected `tool_calls` or `final`)
- `text` (string)

Notes:

- one assistant turn can emit one `AGENT_ASSISTANT_MESSAGE`
- `message_type = "tool_calls"` means the same turn also emitted one or more tool calls
- `message_type = "final"` means the turn ended with assistant content and no tool calls
- if the provider returns no visible content, this event is omitted for that turn
- `sequence` should match the `assistant_message` entry in persisted `agent_context`

## `AGENT_TOOL_CALL`

Emitted when the agent loop decides to execute one tool call.

```json
{
  "id": "evt-001",
  "type": "AGENT_TOOL_CALL",
  "run_id": "bf1c9390-04f7-49c8-89dd-ccb6ad4a714c",
  "created_at": "2026-04-27T10:00:00Z",
  "payload": {
    "step": "support_agent",
    "step_type": "agent",
    "turn_id": "turn-1",
    "sequence": 33,
    "parent_sequence": 32,
    "tool_call_id": "call-1",
    "tool": "shell",
    "args": {
      "command": "git status --short"
    }
  }
}
```

Required payload fields:

- `step` (string)
- `step_type` (string, expected `agent`)
- `turn_id` (string)
- `sequence` (integer, sequence of the persisted `agent_context` entry)
- `tool_call_id` (string)
- `tool` (string)
- `args` (object)

Optional payload fields:

- `parent_sequence` (integer, sequence of the `AGENT_ASSISTANT_MESSAGE` that introduced the tool block)

Notes:

- `args` is observable payload; sensitive data must be redacted before event append.
- when one assistant response contains multiple `tool_calls`, one `AGENT_TOOL_CALL` event is emitted per call
- `turn_id` can repeat across events; `tool_call_id` is the per-call correlation key
- `parent_sequence` links the tool call to the assistant message of the same turn when the turn was `content + tool_calls`
- when the turn was tool-only, `parent_sequence` is omitted

## `AGENT_TOOL_RESULT`

Emitted when the tool call completes (success or failure).

```json
{
  "id": "evt-002",
  "type": "AGENT_TOOL_RESULT",
  "run_id": "bf1c9390-04f7-49c8-89dd-ccb6ad4a714c",
  "created_at": "2026-04-27T10:00:01Z",
  "payload": {
    "step": "support_agent",
    "step_type": "agent",
    "turn_id": "turn-1",
    "sequence": 34,
    "parent_sequence": 32,
    "tool_call_id": "call-1",
    "tool": "shell",
    "context_ref": "agent_context:8f2be0f9-940a-4730-9ad8-5d13d73859b0",
    "output": {
      "text": "M src/skiller/interfaces/tui/screen/render.py",
      "value": {
        "ok": true,
        "exit_code": 0,
        "stdout": "M src/skiller/interfaces/tui/screen/render.py\n",
        "stderr": ""
      },
      "body_ref": null
    }
  }
}
```

Required payload fields:

- `step` (string)
- `step_type` (string, expected `agent`)
- `turn_id` (string)
- `sequence` (integer, sequence of the persisted `agent_context` entry)
- `tool_call_id` (string)
- `tool` (string)
- `context_ref` (string, stable reference to full agent context entry payload)
- `output` (object, runtime output envelope)

Optional payload fields:

- `parent_sequence` (integer, sequence of the `AGENT_ASSISTANT_MESSAGE` that introduced the tool block)

Output envelope follows [`../events/runtime-events.md`](../events/runtime-events.md):

```json
{
  "text": "...",
  "value": {},
  "body_ref": null
}
```

When JSON truncation applies, `output.value` is replaced with a truncation preview object:

```json
{
  "truncated": true,
  "preview": "..."
}
```

## Full Result Resolution

`AGENT_TOOL_RESULT` carries an observable output payload.

The full persisted tool result body is resolved through `context_ref` (not through
`output.body_ref`, which is reserved for step execution outputs in `execution_outputs`).

`tool_call_id` should match:

- the `tool_call_id` in the paired `AGENT_TOOL_CALL`
- the `tool_call_id` persisted in `agent_context.tool_call`
- the `tool_call_id` persisted in `agent_context.tool_result`

`sequence` and `parent_sequence` should match:

- the `sequence` of the persisted `agent_context.tool_result`
- the `sequence` of the persisted `agent_context.assistant_message` that introduced the tool block, when that message exists

## Multi-Tool Turns

When one assistant response contains more than one native `tool_call`:

- all events share the same `turn_id`
- all child events share the same `parent_sequence` when there is assistant content in the turn
- each tool call uses a distinct `tool_call_id`
- one `AGENT_TOOL_CALL` and one `AGENT_TOOL_RESULT` are emitted per executed tool call
- event order follows tool execution order inside the turn

## Concrete Example

This example shows one complete agent flow with:

1. an assistant message that introduces tool execution
2. a multi-tool turn
3. tool results
4. a final assistant response

### Inferred LLM Response: Initial Tool Turn

```json
{
  "turn_id": "turn-7",
  "content": "I will inspect the branch state and the recent commits before preparing the squash.",
  "tool_calls": [
    {
      "id": "call-1",
      "type": "function",
      "function": {
        "name": "shell",
        "arguments": {
          "command": "git status --short"
        }
      }
    },
    {
      "id": "call-2",
      "type": "function",
      "function": {
        "name": "shell",
        "arguments": {
          "command": "git log --oneline -5"
        }
      }
    }
  ]
}
```

### Emitted Runtime Events

```json
[
  {
    "id": "evt-100",
    "run_id": "run-1",
    "type": "AGENT_ASSISTANT_MESSAGE",
    "created_at": "2026-05-06T14:24:00Z",
    "payload": {
      "step": "support_agent",
      "step_type": "agent",
      "turn_id": "turn-7",
      "sequence": 70,
      "message_type": "tool_calls",
      "text": "I will inspect the branch state and the recent commits before preparing the squash."
    }
  },
  {
    "id": "evt-101",
    "run_id": "run-1",
    "type": "AGENT_TOOL_CALL",
    "created_at": "2026-05-06T14:24:00Z",
    "payload": {
      "step": "support_agent",
      "step_type": "agent",
      "turn_id": "turn-7",
      "sequence": 71,
      "parent_sequence": 70,
      "tool_call_id": "call-1",
      "tool": "shell",
      "args": {
        "command": "git status --short"
      }
    }
  },
  {
    "id": "evt-102",
    "run_id": "run-1",
    "type": "AGENT_TOOL_RESULT",
    "created_at": "2026-05-06T14:24:01Z",
    "payload": {
      "step": "support_agent",
      "step_type": "agent",
      "turn_id": "turn-7",
      "sequence": 72,
      "parent_sequence": 70,
      "tool_call_id": "call-1",
      "tool": "shell",
      "context_ref": "agent_context:entry-72",
      "output": {
        "text": " M docs/agent/agent-event.md",
        "value": {
          "ok": true,
          "exit_code": 0,
          "stdout": " M docs/agent/agent-event.md\n",
          "stderr": ""
        },
        "body_ref": null
      }
    }
  },
  {
    "id": "evt-103",
    "run_id": "run-1",
    "type": "AGENT_TOOL_CALL",
    "created_at": "2026-05-06T14:24:01Z",
    "payload": {
      "step": "support_agent",
      "step_type": "agent",
      "turn_id": "turn-7",
      "sequence": 73,
      "parent_sequence": 70,
      "tool_call_id": "call-2",
      "tool": "shell",
      "args": {
        "command": "git log --oneline -5"
      }
    }
  },
  {
    "id": "evt-104",
    "run_id": "run-1",
    "type": "AGENT_TOOL_RESULT",
    "created_at": "2026-05-06T14:24:02Z",
    "payload": {
      "step": "support_agent",
      "step_type": "agent",
      "turn_id": "turn-7",
      "sequence": 75,
      "parent_sequence": 70,
      "tool_call_id": "call-2",
      "tool": "shell",
      "context_ref": "agent_context:entry-75",
      "output": {
        "text": "0c1ed05 fix alias\nb802817 Add agent steering interrupt flow\nc53a783 Add agent loop runtime config defaults",
        "value": {
          "ok": true,
          "exit_code": 0,
          "stdout": "0c1ed05 fix alias\nb802817 Add agent steering interrupt flow\nc53a783 Add agent loop runtime config defaults\n",
          "stderr": ""
        },
        "body_ref": null
      }
    }
  }
]
```

### Inferred LLM Response: Final Turn

After the tool results are returned to the model, the next assistant response may be final-content-only:

```json
{
  "turn_id": "turn-8",
  "content": "The branch is dirty and the last commits are aligned with the agent runtime and TUI work. I can proceed with the squash.",
  "tool_calls": []
}
```

### Final Assistant Runtime Event

```json
{
  "id": "evt-105",
  "run_id": "run-1",
  "type": "AGENT_ASSISTANT_MESSAGE",
  "created_at": "2026-05-06T14:24:03Z",
  "payload": {
    "step": "support_agent",
    "step_type": "agent",
    "turn_id": "turn-8",
    "sequence": 76,
    "message_type": "final",
    "text": "The branch is dirty and the last commits are aligned with the agent runtime and TUI work. I can proceed with the squash."
  }
}
```

## Redaction and Truncation Policy

Agent tool-loop events must be safe to show in logs and UI:

- redact sensitive keys in `args` and `output` payloads (`token`, `password`, `secret`,
  `api_key`, `authorization`)
- redact common secret token text patterns in free text payloads
- apply configurable truncation before appending events

Initial configuration shape:

```json
{
  "agent": {
    "event_output": {
      "truncate": {
        "enabled": true,
        "max_text_chars": 600,
        "max_json_chars": 4000,
        "max_array_items": 20
      },
      "pii": {
        "enabled": true
      },
      "secrets": {
        "enabled": true
      }
    }
  }
}
```
