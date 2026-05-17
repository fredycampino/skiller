# Agent Architecture

## Status

Current runtime status:

- `agent` V2 first slice is implemented
- prompt-driven tool loop is active
- current tools: `shell`, `notify`
- provider-native tool calling is implemented
- multi-tool turns are supported
- streaming tool-call assembly is still open

## Decision

`agent` is one step type executed by one application use case.

Do not model the agent as a long-lived service or as a provider-specific runtime. The outer run loop
stays in `RunWorkerService`. The inner agent loop stays in `ExecuteAgentStepUseCase`.

## Components

| name | layer | type | responsibility |
| --- | --- | --- | --- |
| `StepType.AGENT` | domain | enum value | makes `agent` a valid YAML step |
| `ExecuteAgentStepUseCase` | application | use case | executes the full agent loop for one rendered step |
| `AgentContextEntry` | domain | model | one append-only context entry |
| `AgentContextStorePort` | domain | port | loads and appends agent context entries |
| `ToolManager` | application | component | validates allowed tools and delegates to application tools |
| `Tool` | domain | contract | common executable tool contract |
| `ToolExecutionPort` | domain | port | executes one agent tool batch |
| `ToolProcessPort` | domain | port | controls OS-backed tool processes |
| `ToolInput` | domain | model | wraps raw tool args and exposes typed helpers |
| `ShellProcessTool`, `NotifyTool` | application | tool | reusable callable capabilities for the agent runtime |
| `AgentToolExecution` | application | service | persists agent tool context and runs process-backed tools |
| `DefaultToolProcessRunner` | infrastructure | adapter | starts, polls, reads, and terminates tool processes |
| `SqliteAgentContextStore` | infrastructure | adapter | persists `agent_context_entries` |

## Runtime Shape

Outer runtime flow:

1. `RenderCurrentStepUseCase` returns `READY + current_step`.
2. `RunWorkerService` emits `STEP_STARTED`.
3. `RunWorkerService` dispatches `ExecuteAgentStepUseCase`.
4. `ExecuteAgentStepUseCase` runs the full internal agent loop.
5. The use case returns one `StepAdvance`.
6. `RunWorkerService` emits `STEP_SUCCESS` or fails the run.

Inner agent flow:

1. Read rendered step config.
2. Append the incoming `task` as `user_message`.
3. Load the persisted agent context window for `context_id`.
4. Build provider-ready messages from `system + window entries`.
5. Ask the LLM for one decision.
6. If the response has no tool calls, append the final `assistant_message`, build `StepExecution`, and return.
7. If the response has tool calls, append the optional assistant `tool_calls` message, append each `tool_call`, execute each tool, append each `tool_result`, and continue.
8. If the loop reaches `max_turns` without a final answer, finish the agent step with `MAX_TURNS_EXHAUSTED`.

## Tool Boundary

The typed tool boundary is shared by normal step executors and the agent runtime.

- a `Tool` executes a capability from a typed request and returns a normalized `ToolResult`
- `ToolInput` validates raw external args and helps build the typed request
- `ToolManager` owns allowlist validation, tool request preparation, policy, and dispatch
- a `ProcessTool` builds a `ToolProcessRequest` and maps `ToolProcessOutput` back to `ToolResult`
- `AgentToolExecution` owns agent context persistence around tool calls and results
- `DefaultToolProcessRunner` owns process lifecycle: `popen`, `poll`, `read`, `terminate`

`ToolManager` must not:

- update the run
- write `StepExecution`
- persist context entries directly
- know `shell` or `notify` internals

Concrete tools must not know:

- YAML step shape
- `CurrentStep`
- `StepExecution`
- `next`
- transcript persistence policy

## Current Tradeoff

The current V2 slice is intentionally provider-agnostic.

Tool-enabled turns are implemented with:

- strict prompt instructions
- native tool decisions when the provider returns `tool_calls`
- transcript reconstruction from persisted context
- process tool execution for shell tools so user interrupts can terminate the running process

This keeps the implementation aligned with provider-native tool calling.

## Remaining Work

Still open:

- streaming `tool_calls` assembly
- later tools such as `mcp`
- explicit `WAITING` semantics for `wait_*` inside the agent loop
- optional force-final-answer recovery when `max_turns` is reached
