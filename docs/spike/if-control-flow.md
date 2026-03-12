# Spike: control de flujo con `switch` y `when`

## Estado

Spike cerrado.

La decision de diseno para `1.0.x` queda fijada en este documento y sus dos primitives ya estan implementadas.

## Decision

No se introduce un step `if`.

El control de flujo condicional se separa en dos steps:

- `switch`: routing por igualdad exacta sobre un valor discreto
- `when`: routing por condiciones ordenadas sobre un valor

Ambos encajan con el runtime actual:

- el run persiste `current` como `step_id`
- el loop despacha por `step.type`
- cada step decide el siguiente `step_id` o completa el run

No hace falta reabrir ahora un rediseño general del runtime para soportar branching básico.

## Motivo

Durante la exploracion original se asumio que el runtime seguia avanzando por indice fisico de `steps`.

Eso ya no describe el estado real del runtime actual. Hoy los steps canonicos ya operan con este contrato:

- si el step declara `next`, actualiza `run.current` con ese `step_id`
- si no declara `next`, el step completa el flujo

Con ese contrato:

- `switch` puede resolver un siguiente `step_id` por igualdad exacta
- `when` puede resolver un siguiente `step_id` evaluando ramas en orden

La necesidad de un step `if` separado deja de ser fuerte.

## Step `switch`

`switch` sirve para enrutar por valor exacto.

Caso canonico: decisiones discretas producidas por `llm_prompt`, `assign` u otro step previo.

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

Semantica:

- evalua `value`
- compara por igualdad exacta contra las claves de `cases`
- si encuentra match, salta al `step_id` correspondiente
- si no encuentra match, salta a `default`

Reglas de v0:

- `value` es obligatorio
- `cases` es obligatorio y debe ser un objeto no vacio
- cada entrada de `cases` apunta a un `step_id`
- `default` es obligatorio

## Step `when`

`when` sirve para evaluar condiciones ordenadas sobre un mismo valor.

Caso canonico: umbrales, rangos simples o branching booleano expresado como una sola rama.

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

Semantica:

- evalua `value`
- recorre `branches` en orden
- la primera rama que cumple gana
- si ninguna cumple, salta a `default`

Reglas de v0:

- `value` es obligatorio
- `branches` es obligatorio y debe ser una lista no vacia
- cada rama define un unico operador y un `then`
- `default` es obligatorio

Operadores candidatos de v0:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`

## `when` como sustituto de `if`

No hace falta introducir un `if` adicional para una sola condicion.

Con una unica rama, `when` ya cubre ese caso:

```yaml
- id: decide_retry
  type: when
  value: "{{results.start.action}}"
  branches:
    - eq: retry
      then: retry_notice
  default: human_notice
```

Esto equivale a:

- si `results.start.action == retry`, ir a `retry_notice`
- en caso contrario, ir a `human_notice`

## Criterio de uso

Usar `switch` cuando:

- el dato ya esta normalizado
- hay un conjunto discreto de valores esperados
- el branching es por igualdad exacta

Usar `when` cuando:

- hace falta evaluar condiciones ordenadas
- hay comparaciones numericas o booleanas simples
- el caso es un `if` binario o una cascada pequena de reglas

## Lo que se descarta en esta fase

- introducir un step `if` separado
- soportar bloques estructurados `if / then / else / endif`
- reintroducir semantica basada en el orden fisico de `steps`
- convertir `switch` en un mini lenguaje de operadores

## Estado actual de implementacion

`switch` ya esta implementado.

`when` ya esta implementado.

## Contrato implementado de `when` v0

Contrato base:

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
- `default`: obligatorio

Regla por rama:

- cada rama define exactamente un operador
- cada rama define `then`
- la primera rama que cumple gana

Operadores de v0:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`

Restricciones de v0:

- `eq` y `ne` comparan por igualdad directa
- `gt`, `gte`, `lt` y `lte` solo aceptan comparacion numerica
- no hay operadores compuestos
- no hay condiciones anidadas
- no hay `value` por rama; el lado izquierdo es siempre el `value` del step

Persistencia y eventos:

- guardar en `context.results[step_id]`:

```json
{"value": 95, "next": "excellent"}
```

- emitir `WHEN_DECISION` con payload minimo:

```json
{"step": "decide_score", "value": 95, "next": "excellent", "branch": 0}
```

La inclusion de `branch` en el evento ayuda a explicar por que rama salio la decision sin inflar `context.results`.

Estado de salida:

- `StepType.WHEN`
- `ExecuteWhenStepUseCase`
- `WHEN_DECISION`
- unit, integration y `cli_when.sh`
- alta en `tests/e2e/cli_all.sh`
- `docs/steps/when.md`
