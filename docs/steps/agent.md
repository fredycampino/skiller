# `agent`

## Status

Partial runtime support, V2 first slice delivered.

Implemented today:

- final-only loop when `tools` is omitted
- persisted `user_message` and `assistant_message`
- tool-enabled loop with `shell` and `notify`
- persisted `tool_call` and `tool_result`
- repeated turns up to `max_turns`
- hardened prompt instructions for tool-enabled turns
- raw-response excerpt in invalid JSON errors for debugging

Not implemented yet:

- `mcp.*`
- `wait_*`
- provider-native tool calling
- force-final-answer recovery when `max_turns` is reached

## Goal

`agent` runs an agent-style loop inside one skill step.

The step receives a task, maintains persisted agent context, asks the LLM for turns, executes
selected tools, appends tool results, and finishes when the LLM produces a final response.

The YAML author should not have to wire separate context load, LLM turn, tool call, and context
append steps manually.

## Shape

```yaml
- agent: support_agent
  system: |
    You are a support assistant.
  task: '{{output_value("ask_user").payload.text}}'
  tools:
    - shell
    - notify
  context_id: '{{inputs.thread_id}}'
  max_turns: 8
  next: finish
```

Minimal shape:

```yaml
- agent: support_agent
  system: |
    You are a support assistant.
  task: '{{output_value("ask_user").payload.text}}'
  tools:
    - shell
  next: finish
```

## Fields

- `system` is required. It is the instruction sent to the LLM for each agent turn.
- `task` is required. It is the latest user message or task text for this run. It supports existing
  template expressions such as `output_value(...)`.
- `tools` is optional. When omitted, the runtime keeps the current final-only behavior.
- `tools` must be a list when present. It declares the tools the agent may choose.
- `context_id` is optional. It selects the persisted agent context. When omitted, the runtime uses
  the default context for the current run.
- `max_turns` is optional. It limits the number of LLM decision turns inside this single step.
  Default: `1`.
- `next` is optional. When present, execution continues to this step after the agent produces a
  final response.

## Naming

- `system`: stable agent instruction from the step config.
- `task`: current user request rendered from the skill context.
- `entries`: persisted `AgentContext` entries loaded from the agent context table.
- `messages`: provider-ready LLM input built from `system + entries`.

Do not use `prompt` for `agent`. Unlike `llm_prompt`, an agent turn is built from structured
messages, not one prompt string.

## Runtime Semantics

The `agent` step owns the full loop internally:

1. Append `task` as a user message to the selected `context_id`.
2. Load current `AgentContext.entries`.
3. Build LLM `messages` from `system + entries`.
4. Ask the LLM for one turn.
5. If the LLM returns a final response, append it and finish the step.
6. If the LLM selects a tool, execute the tool, append the tool call and tool result, then repeat.
7. Fail the step if `max_turns` is reached before a final response.

Internal loop:

```text
append user_message(task)

while turn_count < max_turns:
  entries = load_agent_context(run_id, context_id)
  messages = build_agent_messages(system, entries)
  turn = execute_llm_turn(messages, tools)

  if turn is final_response:
    append assistant_message(turn)
    finish step

  if turn.type == "tool_call":
    append tool_call(turn)
    result = execute_agent_tool(turn.tool, turn.args)
    append tool_result(result)

fail step with stop_reason = "max_turns"
```

`system`, `tools`, `max_turns`, and `next` come from the step config. They are not stored as
`AgentContext` entries.

## Current Tool Slice

The first runtime slice supports only:

- `shell`
- `notify`

Later tool names such as `mcp.<server>` or `wait_*` are still design work.

## Message Reconstruction

The runtime rebuilds provider-ready `messages` from persisted context entries on every turn.

Current mapping:

- `user_message` -> `{"role": "user", "content": "<text>"}`
- `assistant_message` -> `{"role": "assistant", "content": "<text>"}`
- `tool_call` -> `{"role": "assistant", "content": "<serialized payload>"}`
- `tool_result` -> `{"role": "user", "content": "<serialized payload>"}`

`tool_call` and `tool_result` are currently serialized as sorted JSON payloads and inserted back
into the transcript. This keeps the loop provider-agnostic for the first slice and avoids coupling
the runtime to provider-specific native tool APIs.

## Turn Contract

When `tools` is omitted, the runtime still accepts the existing final-only behavior from
`LLMPort.generate(...)`. A plain string response is valid and is stored as the final answer.

When `tools` is present, the model must return JSON only for tool calls.

The runtime also strips common wrappers such as Markdown fences and triple-quoted `json` blocks
before parsing. The canonical contract remains the JSON object itself.

Tool call:

```json
{
  "type": "tool_call",
  "tool": "shell",
  "args": {
    "command": "pytest -q"
  }
}
```

Direct final response:

```text
Done.
```

Historical compatibility:

```json
{
  "type": "success",
  "text": "Done."
}
```

The runtime ignores unknown extra fields. The only required structured fields are:

- `type`
- `tool` for `tool_call`
- `args` optional object for `tool_call`

Tool failures are reported back to the model through `tool_result`. They are not a terminal agent
response type in this first slice. The model must decide whether to try another tool or continue
reasoning until it can emit a final response or the runtime reaches `max_turns`.

If parsing still fails, the runtime error includes a short raw-response excerpt to make provider
debugging easier.

## Output

Like other steps, `agent` stores a normalized `output` object. The `data` object is nested under
`output.value` in persistence.

Successful final response:

```json
{
  "output": {
    "text": "Done.",
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

`output_value("support_agent")` returns the `output.value` object:

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

Template access:

```text
{{output_value("support_agent").data.final.text}}
{{output_value("support_agent").data.stop_reason}}
{{output_value("support_agent").data.turn_count}}
```

Reached turn limit:

```json
{
  "error": "Agent step 'support_agent' reached max_turns before producing a final answer"
}
```

Reaching `max_turns` currently fails the step before storing a final step output. A future
`force_answer` mechanism may allow the runtime to ask for one forced final answer before failing.

## Persistence

The observable result of the `agent` step is stored in `runs.step_executions_json` like other steps.

Agent memory should not be stored only in `runs.step_executions_json`. That column is indexed by
`step_id`, so repeated agent turns would overwrite prior values.

Preferred persistence direction:

- add a dedicated append-only agent context table, described in
  [`../db/agent-context.md`](../db/agent-context.md)
- key entries by `run_id`, `context_id`, sequence, and idempotency key
- keep `runs.step_executions_json` for the observable result of the `agent` step
- store each memory entry payload in the agent context table; payloads may be large

## Internal Components

The public `agent` step can be backed by internal use cases with narrower responsibilities:

- `LoadAgentContextUseCase` loads entries for `context_id`.
- `AppendAgentContextUseCase` appends user messages, tool calls, tool results, and final assistant
  messages.
- `ExecuteLlmTurnUseCase` asks the LLM to either select a tool or produce a final response.
- `ToolManager` validates the allowlist, adapts raw args, and dispatches one tool call.

These names are implementation guidance, not YAML step types.
