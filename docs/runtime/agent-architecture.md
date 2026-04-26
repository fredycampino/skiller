# Agent Architecture

## Status

Current runtime status:

- `agent` V2 first slice is implemented
- prompt-driven tool loop is active
- current tools: `shell`, `notify`
- provider-native tool calling is not implemented yet

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
| `AgentContextStorePort` | application port | port | loads and appends agent context entries |
| `ToolManager` | application | component | validates allowed tools and delegates to application tools |
| `Tool` | domain | contract | common executable tool contract |
| `ToolAdapter` | application | component | adapts raw args into typed tool requests |
| `ShellTool`, `NotifyTool` | application | tool | reusable callable capabilities |
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
3. Load persisted agent context for `run_id + context_id`.
4. Build provider-ready messages from `system + entries`.
5. Ask the LLM for one decision.
6. If the decision is `success`, append `assistant_message`, build `StepExecution`, and return.
7. If the decision is `tool_call`, append `tool_call`, execute the selected tool, append `tool_result`, and continue.
8. If the loop reaches `max_turns` without `success`, fail the step.

## Tool Boundary

The tool boundary is shared by normal step executors and the agent runtime.

- a `Tool` executes a capability from a typed request and returns a normalized `ToolResult`
- a `ToolAdapter` validates raw external args and builds the typed request
- `ToolManager` owns allowlist validation and dispatch

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
- one JSON decision per turn
- transcript reconstruction from persisted context

This avoids coupling the first implementation to provider-specific native tool calling APIs.

## Remaining Work

Still open:

- provider-native tool calling
- later tools such as `mcp`
- explicit `WAITING` semantics for `wait_*` inside the agent loop
- optional force-final-answer recovery when `max_turns` is reached
