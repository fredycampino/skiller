# System Diagram

## 1. Arquitectura

```text
                    imports

  +---------------------------+
  | Interfaces                |
  | - CLI                     |
  | - tools/webhooks app      |
  +-------------+-------------+
                |
                v
  +-------------+-------------+
  | Application               |
  | - RuntimeApplicationService
  | - QueryService            |
  | - Use cases               |
  | - Ports                   |
  +------+------+-------------+
         |      |
 imports |      | implements ports / called by services
         v      v
  +------+--+  +-------------------------+
  | Domain  |  | Infrastructure          |
  | Models  |  | - SQLite                |
  | Status  |  | - Skill runner          |
  | Context |  | - MCP adapters          |
  +---------+  +-------------------------+
```

## 2. Runtime principal

```text
  skiller run
      |
      v
  RuntimeController.run(...)
      |
      v
  RuntimeApplicationService.start_run(...)
      |
      v
  StartRunUseCase
      |
      v
  store.create_run(...)
      |
      v
  GetStartStepUseCase
      |
      v
  _run_steps_loop(run_id)
      |
      v
  RenderCurrentStepUseCase
      |
      +--> READY + assign ------> ExecuteAssignStepUseCase
      |                              |
      |                              +--> next -> loop sigue
      |                              |
      |                              +--> sin next -> CompleteRunUseCase
      |
      +--> READY + llm_prompt --> ExecuteLlmPromptStepUseCase
      |                              |
      |                              +--> next -> loop sigue
      |                              |
      |                              +--> sin next -> CompleteRunUseCase
      |
      +--> READY + mcp ---------> RenderMcpConfigUseCase
      |                              |
      |                              v
      |                       ExecuteMcpStepUseCase
      |                              |
      |                              +--> next -> loop sigue
      |                              |
      |                              +--> sin next -> CompleteRunUseCase
      |
      +--> READY + notify ------> ExecuteNotifyStepUseCase
      |                              |
      |                              +--> next -> loop sigue
      |                              |
      |                              +--> sin next -> CompleteRunUseCase
      |
      +--> READY + wait_webhook -> ExecuteWaitWebhookStepUseCase
      |                              |
      |                              +--> next -> loop sigue
      |                              |
      |                              +--> sin next -> CompleteRunUseCase
      |                              |
      |                              +--> waiting -> return
      |
      +--> INVALID_* / error -------> FailRunUseCase
      |
      +--> RUN_NOT_FOUND / DONE / WAITING / CANCELLED / SUCCEEDED / FAILED
                                     -> return
```

## 3. Flujo de webhooks

```text
  HTTP POST /webhooks/{webhook}/{key}
      |
      v
  tools/webhooks/app.py
      |
      +--> valida firma con webhook_registrations
      |
      v
  launcher.receive_webhook(...)
      |
      v
  python -m skiller webhook receive ...
      |
      v
  RuntimeController.receive_webhook(...)
      |
      v
  RuntimeApplicationService.handle_webhook(...)
      |
      v
  HandleWebhookUseCase
      |
      +--> persiste webhook
      +--> deduplica
      +--> devuelve run_ids
      |
      v
  ResumeRunUseCase
      |
      v
  _run_steps_loop(run_id)
      |
      v
  ExecuteWaitWebhookStepUseCase
      |
      +--> puede dejar el run en `WAITING`
      +--> o resolver el wait y mover `current` con `next`
```

## 4. Registro de webhooks

```text
  skiller webhook register <webhook>
      |
      v
  RegisterWebhookUseCase
      |
      v
  webhook_registrations
      |
      +--> webhook
      +--> secret
      +--> enabled
      +--> created_at

  skiller webhook remove <webhook>
      |
      v
  RemoveWebhookUseCase
      |
      v
  webhook_registrations
```
