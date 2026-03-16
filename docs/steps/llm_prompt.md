# `llm_prompt`

## Status

Implemented and active in the new loop based on `current + start/next`.

## Goal

`llm_prompt` is the canonical LLM step for the first version.

It should cover:
- summarization
- classification
- data extraction
- proposing a next action
- writing a structured response

The difference between use cases should come from:
- the `prompt`
- the `system`
- the output `schema`

## Minimal Shape

```yaml
- id: start
  type: llm_prompt
  system: |
    You are a technical analyst.
    Respond only with valid JSON.
  prompt: |
    Analyze this error:
    {{results.test_run.stderr}}
  output:
    format: json
    schema:
      type: object
      required: [summary, severity, next_action]
      properties:
        summary:
          type: string
        severity:
          type: string
          enum: [low, medium, high]
        next_action:
          type: string
          enum: [retry, ask_human, fail]
  next: done
```

## Rendering

`llm_prompt` follows the current runtime pattern:

- `RenderCurrentStepUseCase` renders the full step
- `system` is renderable
- `prompt` is renderable
- any string inside the step is renderable

Supported placeholders:
- `{{inputs...}}`
- `{{results...}}`

## Output

The output must always be `json`.

This first version does not support free-form text output.

The expected result is stored in:

```yaml
results.<step_id>
```

Example:

```yaml
results.start.summary
results.start.severity
results.start.next_action
```

## Format Restriction

The contract must not rely on the prompt alone.

The restriction must come from:
- `output.format: json`
- `output.schema`

The expected executor flow is:

1. take the already rendered `CurrentStep`
2. call the LLM with `system` + `prompt`
3. parse JSON
4. validate it against `schema`
5. if valid, store the result
6. if `next` exists, move `current` to that `step_id`
7. if invalid, fail the step with an explicit error

## Use Case

Current responsibility:

- execute the `llm_prompt` step
- validate JSON against the schema
- store the result in `context.results[step_id]`
- emit `LLM_PROMPT_RESULT`
- emit `LLM_PROMPT_ERROR` when needed
- advance `current` with `next` or complete the run if `next` does not exist

## Complementary Steps

### `assign`

`assign` already exists as a pure mapper for cleaning up or deriving values from the LLM result.

Example:

```yaml
- id: assign_decision
  type: assign
  values:
    next_action: "{{results.analyze_issue.next_action}}"
    severity: "{{results.analyze_issue.severity}}"
```

### `switch` or `when`

Use `switch` or `when` to branch from the LLM result.

Example:

```yaml
- id: check_decision
  type: switch
  value: "{{results.assign_decision.next_action}}"
  cases:
    retry: retry_path
    ask_human: ask_human_path
  default: fail_path
```

## Recommended Direction

Recommended sequence from the current state:

1. use `llm_prompt` to produce structured output
2. use `assign` to normalize or simplify results
3. use `switch` or `when` to branch without turning `llm_prompt` into a step with internal logic

The intent is still to avoid a large family of LLM-specific steps before validating a simple and strong contract.
