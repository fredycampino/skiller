# Agent Failure Retry Spike

## Context

A provider setup flow can create the MiniMax agent config and secret placeholder,
then ask the user to edit the secret file and type `ok`.

After `ok`, the flow runs a basic agent step:

```yaml
- agent: verify_minimax
  system: |
    You are a configuration check agent.
    Reply with one short sentence.
  task: "Say that the MiniMax agent configuration works."
  tools: []
  max_turns: 1
  next: done
```

The goal is to verify that the configured provider, model, base URL, and API key
actually work before telling the user the setup is ready.

## Previous Behavior

If the MiniMax request succeeds, the flow advances to `done` and the run finishes
as `SUCCEEDED`.

If the provider request fails, the agent step raises. The worker records:

- `STEP_ERROR` for `verify_minimax`
- run status `FAILED`
- `RUN_FINISHED` with `status=FAILED`

Example failure:

```text
Agent 'verify_minimax' LLM request failed: OpenAI request failed: Error code: 401
```

This matched the previous agent step contract. Fatal agent errors failed the run
and did not advance through `next`.

## Implemented Direction

`llm_request_failed` is now treated as a recoverable agent stop. The agent step
records normal output with `data.stop_reason = "llm_request_failed"` and follows
`next`, so onboarding flows can route the user back to edit credentials.

## Problem

For onboarding, this is poor UX.

An invalid or missing API key should not permanently kill the setup flow. The
user should get another chance to edit the secret file and retry the validation.

Today the only path after a failed `agent` step is a failed run. The flow cannot
catch the failure and route back to the confirmation prompt.

## Needed Capability

We need a mechanism to catch failures from either:

- an `agent` step
- a failed run/step execution

Then the flow should be able to branch to a recovery step, for example:

```yaml
- agent: verify_minimax
  ...
  next: done
  on_error: confirm_minimax_secret
```

The exact API is not decided.

## Spike Questions

- Should failure handling be modeled at the step level, for example `on_error`?
- Should failure handling be modeled at the run level, for example a generic
  recovery route?
- Should only expected/domain failures be catchable, while runtime bugs remain
  fatal?
- How should the error payload be exposed to templates?
- Should caught failures still emit `STEP_ERROR`, or a different recoverable
  event?
- How does this interact with transcript rendering, especially duplicate error
  output from `STEP_ERROR` and `RUN_FINISHED`?
- How does this interact with persisted run status? Does a caught failure keep
  the run `RUNNING`?

## Acceptance Direction

For onboarding, a failed `verify_minimax` should show the provider error, keep
the run alive, and return to:

```text
After editing the key file, type ok
```

The run should only finish as `FAILED` if the failure is not catchable or if the
recovery route itself fails.
