# Runtime Patterns

## Current Runtime Flow

- `start_run` -> `StartRunUseCase`
- loop -> `RenderCurrentStepUseCase`
- `READY + assign` -> `ExecuteAssignStepUseCase`
- `READY + notify` -> `ExecuteNotifyStepUseCase`
- `READY + llm_prompt` -> `ExecuteLlmPromptStepUseCase`
- `READY + mcp` -> `RenderMcpConfigUseCase` -> `ExecuteMcpStepUseCase`
- `READY + wait_webhook` -> `ExecuteWaitWebhookStepUseCase`
- `DONE` -> `CompleteRunUseCase`
- `INVALID_*` or error -> `FailRunUseCase`

## Webhook Runtime Flow

- webhook input arrives already normalized
- `HandleWebhookUseCase` persists the webhook and returns matching `run_ids`
- `ResumeRunUseCase` marks a waiting run as `RUNNING`
- the service re-enters `_run_steps_loop(run_id)`
- `ExecuteWaitWebhookStepUseCase` is the owner of leaving the wait:
  - if no matching webhook event exists, it leaves the run in `WAITING`
  - if the event exists, it writes `results[step_id]`, advances the step, and continues the loop

## Waiting Semantics

- `wait_webhook` is not consumed when the run first enters `WAITING`
- while waiting, `current_step` stays on the same `wait_webhook` step
- the step is only consumed once a matching `webhook + key` event exists
- the same waiting step owns resolving itself once the matching event exists
- the webhook must be persisted before any attempt to resume the run
- `wait_webhook` must survive process restarts and machine shutdowns because its state lives in persistence
- `webhook receive` must return a minimal operational response:
  - `accepted`
  - `duplicate`
  - `webhook`
  - `key`
  - `matched_runs`
- if `run --start-webhooks` does not end in `WAITING`, the `webhooks` process must not be started
- if `run --start-webhooks` ends in `WAITING`, the system must try to start the `webhooks` process and fail clearly if it cannot
- the minimal `webhooks` process must expose:
  - `GET /health`
  - `POST /webhooks/{webhook}/{key}`

## Contract Style

- `RenderCurrentStepUseCase` returns a minimal result:
  - `status`
  - `next_step` only when `READY`
- `RenderMcpConfigUseCase` returns a minimal result:
  - `status`
  - `mcp_config`
  - `error`
- `ResumeRunUseCase` returns an explicit result:
  - `RESUMED`
  - `RUN_NOT_FOUND`
  - `NOT_WAITING`

## Use Case Naming

- Prefer explicit names:
  - `RenderMcpConfigUseCase`
  - `ExecuteMcpStepUseCase`
  - `ExecuteNotifyStepUseCase`
  - `ExecuteWaitWebhookStepUseCase`
  - `HandleWebhookUseCase`
  - `ResumeRunUseCase`
  - `CompleteRunUseCase`
  - `FailRunUseCase`

- Avoid vague names when the code is really rendering, executing, completing, or failing something.

## Style Intention

- Prepare data in one step.
- Execute it in the next step.
- Keep the loop declarative.
- Keep invalid cases short and explicit.
- Avoid use case -> use case chains and callback-driven runtime flow.
