# Flujo actual de `run`

## Objetivo
Describir de forma breve el camino real de `RuntimeApplicationService.start_run(...)`.

## Fuente mantenida
El detalle operativo del runtime se mantiene en:

- `.codex/skills/skiller-dev/references/runtime-patterns.md`

Este documento queda como vista rápida del flujo.

## Diagrama

```mermaid
flowchart TB
  A["RuntimeApplicationService.start_run(skill_ref, inputs, skill_source)"] --> B["StartRunUseCase.execute"]
  B --> C["store.create_run(skill_source, skill_ref, skill_snapshot, RunContext)"]
  C --> D["GetStartStepUseCase.execute(run_id)"]
  D --> G["RuntimeApplicationService._run_steps_loop(run_id)"]
  G --> H["RenderCurrentStepUseCase.execute(run_id)"]
  H --> I{"status"}

  I -->|RUN_NOT_FOUND| J["return"]
  I -->|DONE| K["CompleteRunUseCase.execute(run_id)"]
  I -->|CANCELLED/WAITING/SUCCEEDED/FAILED| L["return"]
  I -->|INVALID_SKILL / INVALID_STEP| M["FailRunUseCase.execute(run_id, error)"]
  I -->|READY + assign| A["ExecuteAssignStepUseCase.execute(current_step)"]
  I -->|READY + llm_prompt| P["ExecuteLlmPromptStepUseCase.execute(current_step)"]
  I -->|READY + mcp| R["RenderMcpConfigUseCase.execute(current_step) -> ExecuteMcpStepUseCase.execute(current_step, mcp_config)"]
  I -->|READY + notify| N["ExecuteNotifyStepUseCase.execute(current_step)"]
  I -->|READY + switch| S["ExecuteSwitchStepUseCase.execute(current_step)"]
  I -->|READY + wait_webhook| W["ExecuteWaitWebhookStepUseCase.execute(current_step)"]
  I -->|READY + when| Q["ExecuteWhenStepUseCase.execute(current_step)"]

  A --> H
  P --> H
  R --> H
  N --> H
  S --> H
  W -->|NEXT| H
  W -->|WAITING| L
  Q --> H
```

## Resumen
- `start_run` carga la skill, congela un snapshot y crea el run
- `GetStartStepUseCase` exige un step inicial con `id: start` y fija `run.current`
- `RenderCurrentStepUseCase` ya resuelve el step actual por `run.current`, no por indice
- en esta fase del refactor el loop canonico ya tiene migrados `notify`, `assign`, `switch`, `when`, `llm_prompt`, `mcp` y `wait_webhook`
- `notify`, `assign`, `switch`, `when`, `llm_prompt` y `mcp` avanzan con `next` implícito resuelto por el propio step o completan el run
- `wait_webhook` usa el mismo contrato de ejecución y puede devolver `NEXT`, `COMPLETED` o `WAITING`
- errores o estados inválidos terminan en `FailRunUseCase`
