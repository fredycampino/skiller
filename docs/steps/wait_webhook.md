# `wait_webhook`

## Estado

Diseño funcional activo.

La base del step ya está implementada, pero algunos detalles todavía pueden cambiar durante el desarrollo, sobre todo si aparecen:
- problemas con claves duplicadas `webhook + key`
- necesidades nuevas de correlación
- o cambios en la operación del proceso `webhooks`

## Objetivo

`wait_webhook` permite pausar un run hasta que llegue un evento externo.

Debe servir para:
- dejar el run en `WAITING`
- persistir una espera durable
- reanudar el flujo cuando llegue un webhook con el `webhook + key` esperado

## Shape mínimo

```yaml
- id: start
  type: wait_webhook
  webhook: github-pr-merged
  key: "{{results.create_pr.pr}}"
  next: done
```

## Renderizado

`wait_webhook` sigue el patrón actual del runtime:

- `RenderCurrentStepUseCase` renderiza el step completo
- por tanto:
  - `webhook` es renderizable
  - `key` es renderizable

Los placeholders esperados son los mismos del resto del sistema:
- `{{inputs...}}`
- `{{results...}}`

## Semántica de espera

Cuando el step se ejecuta:

1. si no existe un evento persistido para ese `webhook + key`:
- el run pasa a `WAITING`
- se crea o reutiliza una entrada en `waits`
- `current` se mantiene en este mismo step
- el step no se consume todavía

2. si el evento ya existe:
- el step se resuelve
- se escribe el resultado en `context.results[step_id]`
- si existe `next`, el run mueve `current` a ese step
- si no existe `next`, el run se completa

## Resultado

Cuando el step queda resuelto, el resultado esperado es algo como:

```yaml
results.wait_merge.ok
results.wait_merge.webhook
results.wait_merge.key
results.wait_merge.payload
```

Ejemplo:

```json
{
  "ok": true,
  "webhook": "github-pr-merged",
  "key": "42",
  "payload": {
    "merged": true
  }
}
```

## Recepción del webhook

La recepción mínima del sistema hoy es:

```text
POST /webhooks/{webhook}/{key}
```

El evento recibido debe:
- quedar persistido primero
- y solo después intentar reanudar el run

## Reanudación

El flujo esperado es:

1. llega el webhook
2. se persiste el evento
3. `HandleWebhookUseCase` encuentra runs candidatos
4. `ResumeRunUseCase` deja el run reanudable
5. el runtime vuelve a entrar al loop
6. `ExecuteWaitWebhookStepUseCase` encuentra el evento persistido y resuelve el step

## Use case esperado

Nombre actual:

- `ExecuteWaitWebhookStepUseCase`

Responsabilidad:
- ejecutar el step `wait_webhook`
- dejar el run en `WAITING` si no existe evento
- resolver el mismo step si el evento ya existe
- devolver `NEXT`, `COMPLETED` o `WAITING` al loop

## Reglas funcionales importantes

- un step de espera no debe consumirse antes de resolverse
- el mismo step de espera debe ser dueño de resolverse cuando el evento ya existe
- el webhook debe persistirse antes de intentar reanudar el run
- el estado de espera debe sobrevivir reinicios del proceso y apagados de la máquina

## Dirección actual

La base actual usa correlación por:

- `webhook`
- `key`

Y deja pendiente una decisión importante:

- qué hacer cuando existen claves duplicadas `webhook + key`
