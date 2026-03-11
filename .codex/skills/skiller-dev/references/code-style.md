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

## Avoid

- Nested control flow when a flat sequence reads better.
- DTOs with many loosely related optional fields.
- Recomputing or reloading data if it can be prepared once upstream.
- Fallback-heavy behavior that makes the contract ambiguous.
- Strings as hidden enums.
- `bool` returns when the outcome has more than two real semantic states.
- Names like `dispatch` or `process` when the code is doing something more specific.
