# Step `switch`

## Objetivo

`switch` enruta la ejecucion al siguiente `step_id` segun igualdad exacta sobre un valor ya normalizado.

## Contrato v0

```yaml
- id: decide_action
  type: switch
  value: "{{results.start.action}}"
  cases:
    retry: retry_notice
    ask_human: human_notice
    done: done_notice
  default: unknown_action
```

Campos:

- `value`: obligatorio
- `cases`: obligatorio, objeto no vacio con forma `valor -> step_id`
- `default`: obligatorio, `step_id` de fallback

## Semantica

- evalua `value`
- compara por igualdad exacta contra las claves de `cases`
- si hay match, mueve `run.current` al `step_id` asociado
- si no hay match, mueve `run.current` a `default`

## Persistencia

Guarda en `context.results[step_id]`:

```json
{"value": "retry", "next": "retry_notice"}
```

Tambien emite el evento:

```json
{"step": "decide_action", "value": "retry", "next": "retry_notice"}
```

con tipo `SWITCH_DECISION`.
