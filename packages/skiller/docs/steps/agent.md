# `agent`

This page is the YAML contract for the `agent` step.

Agent runtime internals are documented in:

- [`../agent/agent-config.md`](../agent/agent-config.md)
- [`../agent/agent-event.md`](../agent/agent-event.md)
- [`../agent/agent-context.md`](../agent/agent-context.md)
- [`../agent/agent-tools.md`](../agent/agent-tools.md)

## Shape

```yaml
- agent: support_agent
  system: |
    You are a support assistant.
  task: '{{output_value("ask_user").payload.text}}'
  tools:
    - shell
  max_turns: 8
  next: finish
```

Minimal:

```yaml
- agent: support_agent
  system: |
    You are a support assistant.
  task: '{{output_value("ask_user").payload.text}}'
  next: finish
```

System prompt from a file:

```yaml
- agent: ci_agent
  system:
    file: "./system.md"
  task: '{{output_value("ask_user").payload.text}}'
  tools:
    - shell
  next: ask_user
```

## Fields

- `system` (required): step-specific instruction merged with a short runtime base system supplied by Skiller on every turn.
  - string block: inline step-specific system prompt
  - `{file: "./system.md"}`: load the prompt from a UTF-8 file next to the flow file
- `task` (required): user request for this run; templates are allowed.
- `tools` (optional): allowlist of tool names for this step.
- `max_turns` (optional): max LLM decision turns for this step; if omitted, the runtime uses `loop.max_turns` from `agent.json`.
- `next` (optional): next step after the agent step completes normally.

`system.file` must be a relative path inside the flow directory. Absolute paths
and paths escaping the flow directory are rejected.

Runtime-only limits:

- `loop.max_tool_calls`
  - limits how many native `tool_calls` one assistant response may contain
  - this is configured in `agent.json`, not in the step YAML

## Runtime Base System

The runtime always prepends a short built-in system instruction before the step's
own `system` text.

That built-in instruction covers the common contract:
- the assistant is Skiller inside a step-based runtime
- reply in the user's language
- be concise and direct
- use tools only when genuinely helpful
- ask the user before continuing with more tool execution when more work is still needed

The YAML `system` should therefore focus on the step-specific behavior, not on
repeating the generic runtime contract.

## Turn Contract

When `tools` is omitted, plain final text is accepted.

When `tools` is present, the provider must return native `tool_calls`.

Final response:

```text
Done.
```

Tool failures are returned through `tool_result`; they are not terminal by themselves.

## Output

The `agent` step stores a normal `StepExecution` output in runtime context.
It does not create `WAITING` by itself. If the agent should wait for user input,
the next explicit wait step is responsible for that.

Only non-fatal agent finishes create this output. Fatal agent failures do not
create a normal `StepExecution`; they raise from the step execution path and the
runtime records the step/run failure.

The output follows the standard output envelope:

```json
{
  "output": {
    "text": "Done.",
    "text_ref": "data.final",
    "value": {
      "data": {
        "context_id": "ctx-123",
        "final": "Done.",
        "turn_count": 3,
        "tool_call_count": 2,
        "stop_reason": "final",
        "usage": {
          "prompt_tokens": 123,
          "completion_tokens": 45,
          "total_tokens": 168,
          "provider": "minimax",
          "model": "MiniMax-M2.5"
        }
      }
    },
    "body_ref": null
  }
}
```

`output.value` always contains a `data` object. The `data` object has one
of two typed shapes.

Final output:

```json
{
  "data": {
    "context_id": "ctx-123",
    "final": "Done.",
    "turn_count": 3,
    "tool_call_count": 2,
    "stop_reason": "final",
    "usage": {
      "prompt_tokens": 123,
      "completion_tokens": 45,
      "total_tokens": 168,
      "provider": "minimax",
      "model": "MiniMax-M2.5"
    }
  }
}
```

Stop output:

```json
{
  "data": {
    "context_id": "ctx-123",
    "message": "Agent stopped after reaching max turns.",
    "turn_count": 8,
    "tool_call_count": 2,
    "stop_reason": "max_turns_exhausted"
  }
}
```

### Output Fields

- `data.context_id`
  - generated agent context id attached to the current `run_id + agent_id`
- `data.final`
  - final assistant answer; only present when `stop_reason = "final"`
- `data.message`
  - stop explanation; present when `stop_reason` is not `"final"`
- `data.turn_count`
  - number of LLM turns consumed by this step execution
- `data.tool_call_count`
  - number of tool calls executed by this step execution
- `data.stop_reason`
  - terminal reason for this step execution
- `data.usage`
  - optional latest LLM usage for the agent step
  - present when the LLM provider returned usage for the last response
  - includes `prompt_tokens`, `completion_tokens`, `total_tokens`, `provider`, and `model`
  - this is copied into the `STEP_SUCCESS` output; detailed per-entry usage still lives in agent context

### `stop_reason`

Current values:

- `final`
  - normal final assistant answer
- `interrupted`
  - the current tool turn was interrupted through steering, then the agent step
    finalized and the flow continued through `next`
- `max_turns_exhausted`
  - the step consumed its turn budget without a final answer, then finalized and
    the flow continued through `next`
- `config_invalid`
  - the agent config could not be loaded or validated, then finalized and the
    flow continued through `next`

These `stop_reason` values are non-fatal. The step completes normally and the
runtime follows `next` when it is present.

Successful final response:

```json
{
  "output": {
    "text": "Done.",
    "text_ref": "data.final",
    "value": {
      "data": {
        "context_id": "ctx-123",
        "final": "Done.",
        "turn_count": 3,
        "tool_call_count": 2,
        "stop_reason": "final",
        "usage": {
          "prompt_tokens": 123,
          "completion_tokens": 45,
          "total_tokens": 168,
          "provider": "minimax",
          "model": "MiniMax-M2.5"
        }
      }
    },
    "body_ref": null
  }
}
```

`output_value("support_agent")` returns `output.value`:

```json
{
  "data": {
    "context_id": "ctx-123",
    "final": "Done.",
    "turn_count": 3,
    "tool_call_count": 2,
    "stop_reason": "final",
    "usage": {
      "prompt_tokens": 123,
      "completion_tokens": 45,
      "total_tokens": 168,
      "provider": "minimax",
      "model": "MiniMax-M2.5"
    }
  }
}
```

Template examples:

```text
{{output_value("support_agent").data.final}}
{{output_value("support_agent").data.stop_reason}}
{{output_value("support_agent").data.turn_count}}
{{output_value("support_agent").data.usage.total_tokens}}
{{output_value("support_agent").data.usage.model}}
```

Interrupted tool turn:

```json
{
  "output": {
    "text": "",
    "value": {
      "data": {
        "context_id": "ctx-123",
        "message": "Agent execution interrupted.",
        "turn_count": 1,
        "tool_call_count": 0,
        "stop_reason": "interrupted"
      }
    },
    "body_ref": null
  }
}
```

Reached turn limit:

```json
{
  "output": {
    "text": "",
    "value": {
      "data": {
        "context_id": "ctx-123",
        "message": "Agent stopped after reaching max turns.",
        "turn_count": 8,
        "tool_call_count": 2,
        "stop_reason": "max_turns_exhausted"
      }
    },
    "body_ref": null
  }
}
```

Invalid config:

```json
{
  "output": {
    "text": "Provider 'minimax' does not support model='bad-model'.",
    "text_ref": "data.message",
    "value": {
      "data": {
        "context_id": "",
        "message": "Provider 'minimax' does not support model='bad-model'. (PROVIDER_MODEL_UNSUPPORTED)",
        "turn_count": 0,
        "tool_call_count": 0,
        "stop_reason": "config_invalid"
      }
    },
    "body_ref": null
  }
}
```

In these cases, the `agent` step still completes normally. The runtime then follows
the step's `next` transition. A later `wait_input` or `wait_channel` step is what
creates `WAITING`, not the `agent` step itself.

Exceeded per-turn tool limit:

- if one assistant response contains more than `loop.max_tool_calls` tool calls,
  the runtime does not execute any of them
- instead, it appends corrective feedback to the agent context and asks the LLM again

## Fatal Exits

Fatal exits do not produce the normal `agent` step output shown above. They raise
from the agent step use case, so the runtime records the step/run failure instead
of advancing through `next`.

Current fatal cases:

- `llm_request_failed`
  - the configured LLM client returns `ok = false`
  - no final assistant message is persisted
- `tool_execution_failed`
  - tool preparation/execution hits an unexpected request or policy exception
  - already-persisted context before the failure remains in the agent context
  - no final assistant message is persisted
- `invalid_final_message`
  - the LLM finishes without usable final text when a final answer is required
  - no final assistant message is persisted

Schema errors in the YAML step itself are also fatal, for example missing
`system`, missing `task`, invalid `tools`, unsupported `context_id`, or an empty
`next` value.
