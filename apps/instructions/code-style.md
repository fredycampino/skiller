# Code Style

This file is the canonical source of truth for Skiller code style. Its instructions apply to new
code and to code changed as part of the current work. They define the default style for `domain`,
`application`, interfaces, and infrastructure.

Imperative rules such as **use**, **keep**, and **do not** are requirements. Rules written as
**prefer** describe the default choice; deviate only when the alternative makes the contract or
flow clearer.

## Control Flow

- Keep control flow flat with guard clauses, early returns, and early `continue` statements.
- Establish a shared precondition once instead of repeating it in every branch.
- Avoid nested `if` blocks when a sequence of independent branches reads more clearly.
- Keep short branches inline. Extract a long branch only when it represents a named
  sub-operation or a separate use case.

Preferred:

```python
current_step = result.current_step

if status != CurrentStepStatus.READY or current_step is None:
    continue

if current_step.step_type == StepType.NOTIFY:
    ...
    continue

if current_step.step_type == StepType.MCP:
    ...
    continue
```

Avoid:

```python
if status == CurrentStepStatus.READY and current_step is not None:
    if current_step.step_type == StepType.NOTIFY:
        ...
    elif current_step.step_type == StepType.MCP:
        ...
```

## Boundaries and Normalization

- Validate and normalize external values at the boundary that introduces them. Boundaries include
  parsers, interface mappers, configuration readers, and infrastructure responses.
- Normalize text once. Do not scatter `.strip()` or equivalent cleanup through internal logic.
- After a value crosses a typed boundary, application and domain code should trust its contract
  instead of repeating defensive validation.
- Use `| None` only when absence is part of the domain or operation contract.
- A parser may convert a missing external field to `None`; an internal constructor must require the
  caller to pass that value explicitly.
- Constructor dependencies must be required when the component cannot operate without them. Do not
  make dependencies optional or default them to `None` to preserve old call sites or simplify
  tests.

## Explicit Contracts

- Use an enum when a domain value has a closed set of states.
- Use small typed request and result objects when they make an operation's inputs or outcomes
  explicit.
- Prefer immutable contract objects. Use `frozen=True` unless mutation represents an intentional
  domain transition.
- Model expected business outcomes in the result contract. Do not communicate them through raw
  dictionaries, defensive `None` checks, or generic exceptions.
- Use an exception for invalid input, a violated invariant, or an unexpected failure. Put the
  specific detail in its message instead of creating a separate status for every error variation.
- Return `bool` only when the contract has exactly two semantic outcomes.
- When a state object exposes transition methods such as `finish_*` or `fail_*`, use those methods.
  Do not assign its transition fields directly from outside the object.

## Operation Parameters

- Group parameters because they form one domain operation or concept, not merely to reduce the
  argument count.
- Introduce a semantic request or state object when related values travel together across multiple
  layers, are repeatedly passed together, or must remain consistent as a unit.
- Prefer names such as `AgentRunState`, `CurrentStep`, or `ToolExecutionRequest` over generic
  parameter bags.
- Keep grouped objects focused. Do not create a mutable mega-state object containing unrelated
  operation data.
- Do not store temporary operation state on a singleton or long-lived service to shorten method
  signatures.
- If a stable shape crosses an internal boundary, model it explicitly. Reserve raw
  `dict[str, object]` values for genuinely dynamic data and serialization boundaries.
- Do not reconstruct the same domain fact from primitive fields in several layers. Pass, persist,
  or emit the typed object that already represents it.
- A top-level method should expose the operation's flow rather than repeat plumbing for primitive
  values.

Preferred:

```python
wait_request = ToolProcessWait(
    handle=handle,
    timeout=timeout,
    interrupt=interrupt,
)
wait_result = process_runner.wait(wait_request)
```

Avoid:

```python
wait_result = process_runner.wait(
    handle,
    timeout=timeout,
    run_id=run_id,
    interrupt_signal=interrupt,
)
```

Also avoid moving those values into temporary service state:

```python
self.run_id = run_id
self.interrupt = interrupt
wait_result = process_runner.wait(handle)
```

## Expressions and Helpers

- Prepare non-trivial values in named local variables before passing them to constructors,
  requests, function calls, or return values.
- Split chained transformations when understanding the expression requires tracking several
  operations at once.
- Keep small, obvious conversions inline when they do not obscure the flow.
- Do not extract a helper merely to hide a one-line check or expression.
- Extract a private helper when it names a real sub-operation, removes meaningful duplication, or
  keeps a substantial branch understandable.
- Prepare or load a value once upstream and reuse it when the same fact is needed later.

Preferred:

```python
system = f"{AGENT_RUNTIME_SYSTEM}\n\n{step.system}"
tool_names = list(step.tools)
tool_configs = self.tool_manager.get_tool_configs(tool_names)
tools = tuple(tool_configs)
config = self._apply_step_overrides(config=config, step=step)

return AgentRunnerConfig(
    system=system,
    task=step.task,
    context_id=step.context_id,
    tools=tools,
    config=config,
)
```

Avoid:

```python
return AgentRunnerConfig(
    system=f"{AGENT_RUNTIME_SYSTEM}\n\n{step.system}",
    task=step.task,
    context_id=step.context_id,
    tools=tuple(self.tool_manager.get_tool_configs(list(step.tools))),
    config=self._apply_step_overrides(config=config, step=step),
)
```

## YAML-Driven Behavior

- Keep YAML-driven behavior explicit, validated, and deterministic.
- Do not introduce hidden fallbacks that silently change the meaning of an omitted or invalid
  field.
- Resolve external YAML values into typed internal contracts before executing the operation.
- Given the same workflow snapshot, inputs, and persisted external events, control-flow decisions
  should be reproducible. Any nondeterministic external operation must be explicit in the workflow.

## Naming

- Follow
  [`naming-style.md`](../../packages/skiller/docs/architecture/naming-style.md)
  for ports, infrastructure port implementations, datasources, and mappers.
- Name a value or component for its domain role in the current context.
- Avoid generic names such as `ctx`, `data`, `payload`, `params`, `info`, or `obj` when a more
  precise domain name exists. A conventional name is acceptable when the surrounding contract
  makes its meaning exact.
- Do not use `context` as a generic suffix. Distinguish runtime context, agent context, LLM context,
  and other domain-specific contexts.
- Prefer precise names such as `run`, `turn`, `agent_id`, `context_id`,
  `agent_context_entries`, `tool_request`, or `current_step`.
- Translate a broad outer-layer name at the boundary when the inner component has a more precise
  domain term. For example, translate `step_id` to `agent_id` when entering an agent-specific
  component.
- Names such as `dispatch` or `process` are valid when they describe the actual operation. Prefer a
  more specific domain verb when one exists.

## Package Files

- Use namespace packages for new directories by default; do not add `__init__.py` automatically.
- Add `__init__.py` only for package initialization, an intentional public API through re-exports,
  or a proven tooling or runtime compatibility requirement.
- Do not add a docstring-only `__init__.py`.
