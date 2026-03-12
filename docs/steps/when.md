# Step `when`

## Objetivo

`when` enruta la ejecucion al siguiente `step_id` evaluando ramas en orden sobre un mismo valor.

## Contrato v0

```yaml
- id: decide_score
  type: when
  value: "{{results.score}}"
  branches:
    - gt: 90
      then: excellent
    - gt: 70
      then: good
  default: fail
```

Campos:

- `value`: obligatorio
- `branches`: obligatorio, lista no vacia
- `default`: obligatorio, `step_id` de fallback

Reglas por rama:

- cada rama define exactamente un operador
- cada rama define `then`
- la primera rama que cumple gana

Operadores v0:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`

## Semantica

- evalua `value`
- recorre `branches` en orden
- la primera rama que cumple mueve `run.current` al `step_id` indicado por `then`
- si ninguna cumple, mueve `run.current` a `default`

## Persistencia

Guarda en `context.results[step_id]`:

```json
{"value": 85, "next": "good"}
```

Tambien emite el evento:

```json
{"step": "decide_score", "value": 85, "next": "good", "branch": 1, "op": "gt", "right": 70}
```

con tipo `WHEN_DECISION`.
