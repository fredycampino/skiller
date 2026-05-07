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
  context_id: '{{inputs.thread_id}}'
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

## Fields

- `system` (required): step-specific instruction merged with a short runtime base system supplied by Skiller on every turn.
- `task` (required): user request for this run; templates are allowed.
- `tools` (optional): allowlist of tool names for this step.
- `context_id` (optional): logical memory key inside the run; default is run id.
- `max_turns` (optional): max LLM decision turns for this step; if omitted, the runtime uses `agent.loop.max_turns` from `agent.json`.
- `next` (optional): next step after successful final response.

Runtime-only limits:

- `agent.loop.max_tool_calls`
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
It does not create `WAITING` by itself. If the skill should wait for user input,
the next explicit wait step is responsible for that.

The output follows the standard output envelope:

```json
{
  "output": {
    "text": "Done.",
    "text_ref": "data.final.text",
    "value": {
      "data": {
        "context_id": "thread-1",
        "final": {
          "text": "Done."
        },
        "turn_count": 3,
        "tool_call_count": 2,
        "stop_reason": "success"
      }
    },
    "body_ref": null
  }
}
```

`output.value` always has this shape:

```json
{
  "data": {
    "context_id": "thread-1",
    "final": {
      "text": "Done."
    },
    "turn_count": 3,
    "tool_call_count": 2,
    "stop_reason": "success"
  }
}
```

### Output Fields

- `data.context_id`
  - logical agent context id used for this step
- `data.final.text`
  - final text returned by the agent step
- `data.turn_count`
  - number of LLM turns consumed by this step execution
- `data.tool_call_count`
  - number of tool calls executed by this step execution
- `data.stop_reason`
  - terminal reason for this step execution

### `stop_reason`

Current values:

- `success`
  - normal final assistant answer
- `interrupted`
  - the current tool turn was interrupted through steering, then the agent step
    finalized and the flow continued through `next`
- `max_turns_exhausted`
  - the step consumed its turn budget without a final answer, then finalized and
    the flow continued through `next`

Successful final response:

```json
{
  "output": {
    "text": "Done.",
    "text_ref": "data.final.text",
    "value": {
      "data": {
        "context_id": "thread-1",
        "final": {
          "text": "Done."
        },
        "turn_count": 3,
        "tool_call_count": 2,
        "stop_reason": "success"
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
    "context_id": "thread-1",
    "final": {
      "text": "Done."
    },
    "turn_count": 3,
    "tool_call_count": 2,
    "stop_reason": "success"
  }
}
```

Template examples:

```text
{{output_value("support_agent").data.final.text}}
{{output_value("support_agent").data.stop_reason}}
{{output_value("support_agent").data.turn_count}}
```

Interrupted tool turn:

```json
{
  "output": {
    "text": "Interrupted. Send another message if you want to continue.",
    "text_ref": "data.final.text",
    "value": {
      "data": {
        "context_id": "thread-1",
        "final": {
          "text": "Interrupted. Send another message if you want to continue."
        },
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
    "text": "I reached the turn limit before finishing. Send another message if you want me to continue.",
    "text_ref": "data.final.text",
    "value": {
      "data": {
        "context_id": "thread-1",
        "final": {
          "text": "I reached the turn limit before finishing. Send another message if you want me to continue."
        },
        "turn_count": 8,
        "tool_call_count": 2,
        "stop_reason": "max_turns_exhausted"
      }
    },
    "body_ref": null
  }
}
```

In both cases, the `agent` step still completes normally. The runtime then follows
the step's `next` transition. A later `wait_input` or `wait_channel` step is what
creates `WAITING`, not the `agent` step itself.

Exceeded per-turn tool limit:

- if one assistant response contains more than `agent.loop.max_tool_calls` tool calls,
  the runtime does not execute any of them
- instead, it appends corrective feedback to the agent context and asks the LLM again
