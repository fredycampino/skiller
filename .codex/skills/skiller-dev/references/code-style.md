# Code Style

## Loop Style

- Keep loops flat.
- Use guard clauses and early returns.
- Avoid nested `if` blocks inside loops.
- Avoid duplicating the same condition in multiple branches.
- If a branch grows, extract it to a helper or a use case.

Preferred shape:

```python
current_step = result.current_step
is_ready = status == CurrentStepStatus.READY and current_step

if is_ready and current_step.step_type == StepType.NOTIFY:
    ...
    continue

if is_ready and current_step.step_type == StepType.MCP:
    ...
    continue
```

Before:

```python
if status == CurrentStepStatus.READY and current_step and current_step.step_type == StepType.MCP:
    render_result = self.render_mcp_config_use_case.execute(current_step)
    if render_result.status == RenderMcpConfigStatus.INVALID_CONFIG:
        self.fail_run_use_case.execute(run_id, error=render_result.error or "Invalid MCP config")
        return
    self.execute_mcp_step_use_case.execute(current_step, render_result.mcp_config)
    continue
```

After:

```python
current_step = result.current_step
is_ready = status == CurrentStepStatus.READY and current_step

if is_ready and current_step.step_type == StepType.MCP:
    render_result = self.render_mcp_config_use_case.execute(current_step)
    if render_result.status == RenderMcpConfigStatus.INVALID_CONFIG:
        self.fail_run_use_case.execute(
            run_id,
            error=render_result.error or f"Invalid MCP config for step '{current_step.step_id}'",
        )
        return

    self.execute_mcp_step_use_case.execute(current_step, render_result.mcp_config)
    continue
```

## Preferred Patterns

- Use enums instead of string literals when the set of values is closed.
- Use small result dataclasses for explicit contracts.
- Put detail in the error message, not in a large taxonomy of statuses.
- Prepare data in one step and execute it in the next step.
- Keep YAML-driven behavior explicit and deterministic.

## Parameter Grouping

- If the same group of parameters is passed through 3 or more calls, introduce a small semantic dataclass.
- If several parameters describe one operation, introduce an operation request object instead of growing the method signature.
- Group by operational meaning, not by convenience. Prefer `AgentRunState`, `CurrentStep`, or `ToolExecutionRequest` over generic bags.
- Keep grouping dataclasses small, stable, and preferably `frozen=True`.
- Do not create a mutable mega-state object just to reduce argument count.
- Do not hide operation state in singleton services just to make a call site shorter.
- The top-level method should read as a flow, not as repeated plumbing of primitive fields.

Preferred:

```python
run = self._build_run_state(request)

self._append_initial_user_task(run=run)
entries = self._list_context_entries(run)
tool_request = self._build_tool_execution_request(
    run=run,
    turn_id=turn_id,
    response=response,
    turn_loop=turn_loop,
)
```

Avoid:

```python
self._append_initial_user_task(
    run_id=run_id,
    step_id=step_id,
    context_id=config.context_id,
    task=config.task,
)
```

When a method operates on a process, tool, step, or turn and needs several related
options, model the operation explicitly.

Preferred:

```python
wait_result = process_runner.wait(
    ToolProcessWait(
        handle=handle,
        timeout=timeout,
        interrupt=interrupt,
    )
)
```

Avoid:

```python
wait_result = process_runner.wait(
    handle,
    timeout=timeout,
    run_id=run_id,
    interrupt_signal=signal,
)
```

Also avoid making a service temporarily stateful to reduce arguments:

```python
self.run_id = run_id
wait_result = process_runner.wait(handle, interrupt_signal=self)
```

## Naming

- Names must describe the domain role in the current component.
- Avoid generic names like `ctx`, `data`, `payload`, `params`, `info`, or `obj` unless the surrounding contract already makes the meaning exact.
- Avoid `context` as a generic suffix. In Skiller, `context` is already overloaded by runtime context, agent context, and LLM context.
- Prefer precise names like `run`, `turn`, `agent_id`, `context_id`, `agent_context_entries`, `tool_request`, or `current_step`.
- If an outer layer uses a broader term like `step_id`, translate it at the boundary when the inner component has a better domain term like `agent_id`.

## Avoid

- Nested control flow when a flat sequence reads better.
- DTOs with many loosely related optional fields.
- Recomputing or reloading data if it can be prepared once upstream.
- Fallback-heavy behavior that makes the contract ambiguous.
- Strings as hidden enums.
- `bool` returns when the outcome has more than two real semantic states.
- Names like `dispatch` or `process` when the code is doing something more specific.
- Repeated long argument lists made of primitive values.
- Generic context objects that hide which context is being used.
