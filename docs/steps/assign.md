# `assign`

## Goal

`assign` is a pure mapping step.

It does not call external services, decide branches, or wait for events.
It only takes values that already exist in the run context and stores them in:

```yaml
results.<step_id>
```

## Minimal Shape

```yaml
- id: prepare_issue
  type: assign
  values:
    action: "{{results.analyze_issue.next_action}}"
    summary: "{{results.analyze_issue.summary}}"
```

Expected result:

```yaml
results.prepare_issue.action
results.prepare_issue.summary
```

## Recommended Use

`assign` is useful for:

- renaming fields
- flattening awkward structures
- preparing a clearer object for later steps
- avoiding long paths such as `results.something.very.deep`

## Rendering

`assign` follows the normal runtime rendering rules:

- `RenderCurrentStepUseCase` renders the full step
- any string inside `values` is renderable

Example:

```yaml
- id: prepare
  type: assign
  values:
    action: "{{results.analyze_issue.next_action}}"
    meta:
      severity: "{{results.analyze_issue.severity}}"
      source: "llm"
    tags:
      - triage
      - "{{results.analyze_issue.severity}}"
```

If an entry in `values` is a full placeholder such as `{{results.foo}}`, the renderer keeps the original value when it exists instead of always converting it to a string.

## v0 Restrictions

In this version:

- `values` is mandatory
- `values` must be an object
- `values` must not be empty

It does not support:

- expressions
- comparisons
- functions
- casts
- its own schema validation

If you need logic, that belongs in `switch`, `when`, or a future more expressive step.

## Persistence

`assign` stores the result in:

```yaml
results.<step_id>
```

It also emits:

```text
ASSIGN_RESULT
```

with:

- `step`
- `result`
