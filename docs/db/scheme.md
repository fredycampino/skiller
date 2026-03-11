# DB actual de Skiller

## Objetivo

Describir el estado actual de la base de datos SQLite usada por `Skiller`.

Este documento refleja como esta hoy el esquema real y que representa cada tabla.

Fuente principal:

- [sqlite_state_store.py](/home/fede/develop/py/skiller/src/skiller/infrastructure/db/sqlite_state_store.py)
- [sqlite_webhook_registry.py](/home/fede/develop/py/skiller/src/skiller/infrastructure/db/sqlite_webhook_registry.py)

## Idea general

`Skiller` no persiste el contexto completo del run como un blob unico.

Hoy la persistencia se reparte asi:

- `runs` guarda la identidad del run, su snapshot de skill, su estado y el puntero actual del flujo
- `events` guarda la traza de ejecucion
- `waits` y `webhook_events` guardan el estado operativo de `wait_webhook`
- `webhook_receipts` resuelve deduplicacion de recepcion
- `webhook_registrations` guarda los secretos por canal webhook

El `RunContext.results` se reconstruye leyendo eventos, no desde una columna propia en `runs`.

## Tabla `runs`

Representa un run persistido del runtime.

Columnas actuales:

- `id TEXT PRIMARY KEY`
  - identificador del run
- `skill_source TEXT NOT NULL`
  - origen de la skill
  - hoy suele ser `internal` o `file`
- `skill_ref TEXT NOT NULL`
  - nombre de la skill interna o path del fichero
- `skill_snapshot_json TEXT NOT NULL`
  - snapshot congelado de la skill en JSON
- `status TEXT NOT NULL`
  - estado del run
  - hoy: `CREATED`, `RUNNING`, `WAITING`, `SUCCEEDED`, `FAILED`, `CANCELLED`
- `current TEXT`
  - puntero del run
  - apunta al `id` del step actual
  - es la fuente de verdad del flujo `start/next`
- `inputs_json TEXT NOT NULL DEFAULT '{}'`
  - inputs iniciales del run
- `cancel_reason TEXT`
  - razon de cancelacion, si existe
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `finished_at TEXT`
  - se marca cuando el run termina en `SUCCEEDED`, `FAILED` o `CANCELLED`

Ejemplo de registro:

```json
{
  "id": "run-uuid",
  "skill_source": "file",
  "skill_ref": "tests/e2e/skills/notify_cli_e2e.yaml",
  "status": "SUCCEEDED",
  "current": "start",
  "inputs_json": "{\"issue\": \"dependency timeout\"}",
  "cancel_reason": null
}
```

## Tabla `waits`

Representa una espera activa o resuelta de un step `wait_webhook`.

Columnas actuales:

- `id TEXT PRIMARY KEY`
  - identificador de la espera
- `run_id TEXT NOT NULL`
  - referencia al run
- `step_id TEXT NOT NULL`
  - id del step `wait_webhook`
- `webhook TEXT NOT NULL`
  - canal webhook esperado
- `key TEXT NOT NULL`
  - clave de correlacion
- `status TEXT NOT NULL`
  - hoy se usan al menos `ACTIVE`, `RESOLVED`, `EXPIRED`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `expires_at TEXT`
- `resolved_at TEXT`

Ejemplo de registro:

```json
{
  "id": "wait-uuid",
  "run_id": "run-uuid",
  "step_id": "wait_merge",
  "webhook": "github-pr-merged",
  "key": "42",
  "status": "ACTIVE"
}
```

## Tabla `events`

Es la traza principal del runtime por run.

Cada fila representa un evento de dominio u operativo asociado a `run_id`.

Columnas actuales:

- `id TEXT PRIMARY KEY`
- `run_id TEXT`
  - puede ser `NULL` si hiciera falta un evento no ligado a run, aunque el uso normal hoy es por run
- `type TEXT NOT NULL`
  - tipo de evento
- `payload_json TEXT NOT NULL`
  - payload JSON del evento
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Tipos de evento relevantes hoy:

- `NOTIFY`
- `ASSIGN_RESULT`
- `LLM_PROMPT_RESULT`
- `LLM_PROMPT_ERROR`
- `MCP_RESULT`
- `TOOL_RESULT`
- `WAITING`
- `WAIT_RESOLVED`
- `RUN_FAILED`
- `RUN_FINISHED`
- `RUN_CANCELLED`
- `STEER_RECORDED`

Ejemplo de registro:

```json
{
  "id": "event-uuid",
  "run_id": "run-uuid",
  "type": "ASSIGN_RESULT",
  "payload_json": "{\"step\":\"prepare\",\"result\":{\"action\":\"retry\"}}"
}
```

## Tabla `webhook_receipts`

Se usa para deduplicar recepciones webhook por `dedup_key`.

Columnas actuales:

- `dedup_key TEXT PRIMARY KEY`
- `webhook TEXT NOT NULL`
- `key TEXT NOT NULL`
- `payload_json TEXT NOT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Si una insercion falla por clave primaria, el webhook ya fue procesado como recibo.

## Tabla `webhook_events`

Guarda los eventos webhook ya aceptados por el runtime.

Esta tabla es la que consulta `wait_webhook` para resolver una espera activa.

Columnas actuales:

- `id TEXT PRIMARY KEY`
- `webhook TEXT NOT NULL`
- `key TEXT NOT NULL`
- `payload_json TEXT NOT NULL`
- `dedup_key TEXT NOT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Ejemplo de registro:

```json
{
  "id": "webhook-event-uuid",
  "webhook": "github-pr-merged",
  "key": "42",
  "dedup_key": "provider-delivery-id"
}
```

## Tabla `webhook_registrations`

Guarda la configuracion por canal webhook.

Hoy se usa para validar firma y para registrar o eliminar canales mediante CLI.

Columnas actuales:

- `webhook TEXT PRIMARY KEY`
- `secret TEXT NOT NULL`
- `enabled INTEGER NOT NULL DEFAULT 1`
  - se interpreta como booleano
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Ejemplo de registro:

```json
{
  "webhook": "github-pr-merged",
  "secret": "generated-secret",
  "enabled": 1
}
```

## Como se reconstruye el contexto hoy

La idea importante es esta:

- durante la ejecucion, cada step escribe su resultado en `next_step.context.results`
- para que ese resultado sobreviva a una recarga del run, el step tambien escribe un evento en `events`

Ejemplo real de `assign`:

```python
next_step.context.results[step_id] = result

self.store.append_event(
    "ASSIGN_RESULT",
    {
        "step": step_id,
        "result": result,
    },
    run_id=next_step.run_id,
)
```

La primera linea actualiza el contexto en memoria del run actual.
La llamada a `append_event(...)` es la que deja persistido ese resultado para el futuro.

## Que guarda `runs` y que guarda `events`

La tabla `runs` guarda solo una parte del estado:

- `inputs_json`
- `cancel_reason`
- `status`
- `current`
- `skill_snapshot_json`

La tabla `runs` no tiene una columna propia para `results`.

Por eso, los resultados utiles de los steps se persisten de forma efectiva a traves de `events`.

## Como reconstruye el store el contexto

Cuando `SqliteStateStore.get_run(...)` reconstruye un run:

1. lee `inputs_json` desde `runs`
2. lee `cancel_reason` desde `runs`
3. lee `current` desde `runs`
4. crea un `RunContext(inputs=..., results={})`
5. recorre `events` del run en orden
6. va rellenando `context.results` segun el tipo de evento

Hoy:

- `NOTIFY` reconstruye `results.<step_id> = {ok: true, message: ...}`
- `ASSIGN_RESULT` reconstruye `results.<step_id> = result`
- `LLM_PROMPT_RESULT` reconstruye `results.<step_id> = result`
- `MCP_RESULT` y `TOOL_RESULT` reconstruyen `results.<step_id> = result`
- `WAIT_RESOLVED` reconstruye `results.<step_id> = {ok, webhook, key, payload}`
- `STEER_RECORDED` reconstruye `steering_messages`
- `RUN_CANCELLED` puede rellenar `cancel_reason`

## Ejemplo

Si un run tiene estos eventos:

```json
[
  {
    "type": "LLM_PROMPT_RESULT",
    "payload": {
      "step": "analyze_issue",
      "result": {
        "summary": "Timeout",
        "severity": "low",
        "next_action": "retry"
      }
    }
  },
  {
    "type": "ASSIGN_RESULT",
    "payload": {
      "step": "prepare",
      "result": {
        "action": "retry"
      }
    }
  },
  {
    "type": "NOTIFY",
    "payload": {
      "step": "done",
      "message": "retry"
    }
  }
]
```

Entonces, al hacer `get_run(...)`, el contexto reconstruido queda asi:

```json
{
  "inputs": { "...": "..." },
  "results": {
    "analyze_issue": {
      "summary": "Timeout",
      "severity": "low",
      "next_action": "retry"
    },
    "prepare": {
      "action": "retry"
    },
    "done": {
      "ok": true,
      "message": "retry"
    }
  }
}
```

Consecuencia importante:

- el estado general del run vive en `runs`
- los resultados utiles de los steps viven, en la practica, en `events`
- si un step no escribiera su evento de resultado, ese valor se perderia al volver a cargar el run desde SQLite

## Indices actuales

Indices definidos hoy:

- `idx_runs_status_updated_at` sobre `runs(status, updated_at)`
- `idx_waits_run_status` sobre `waits(run_id, status)`
- `idx_waits_webhook_key_status` sobre `waits(webhook, key, status)`
- `idx_events_run_created_at` sobre `events(run_id, created_at)`
- `idx_webhook_receipts_webhook_key_created_at` sobre `webhook_receipts(webhook, key, created_at)`
- `idx_webhook_events_webhook_key_created_at` sobre `webhook_events(webhook, key, created_at)`

## Notas de diseno del estado actual

1. `current` es el unico puntero persistido del runtime y apunta al `step_id` actual.

2. `skill_snapshot_json` congela la skill completa al arrancar el run.
   Cambios posteriores en el YAML no alteran runs ya creados.

3. `results` no se persiste directamente.
   Se reconstruye a partir de eventos.

4. `webhook_registrations` comparte la misma DB SQLite que el resto del runtime.

5. No hay un sistema de migraciones fuerte.
   El store solo aplica ajustes puntuales de compatibilidad cuando hacen falta y, fuera de eso, se asume que la DB puede resetearse.
