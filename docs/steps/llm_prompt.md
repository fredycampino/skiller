# `llm_prompt`

## Estado

Implementado y operativo dentro del loop nuevo basado en `current + start/next`.

## Objetivo

`llm_prompt` es el step LLM canónico para una primera versión.

Debe servir para:
- resumir
- clasificar
- extraer datos
- proponer una siguiente acción
- redactar una respuesta estructurada

La diferencia entre usos no la marca un tipo distinto de step, sino:
- el `prompt`
- el `system`
- el `schema` de salida

## Shape mínimo

```yaml
- id: start
  type: llm_prompt
  system: |
    Eres un analista técnico.
    Responde solo en JSON válido.
  prompt: |
    Analiza este error:
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

## Renderizado

`llm_prompt` debe seguir el patrón actual del runtime:

- `RenderCurrentStepUseCase` renderiza el step completo
- por tanto:
  - `system` es renderizable
  - `prompt` es renderizable
  - cualquier string dentro del step es renderizable

Los placeholders esperados son los mismos que ya soporta el repo:
- `{{inputs...}}`
- `{{results...}}`

## Salida

La salida debe ser siempre `json`.

No se propone una primera versión con salida libre en texto.

El resultado esperado se guarda en:

```yaml
results.<step_id>
```

Ejemplo:

```yaml
results.start.summary
results.start.severity
results.start.next_action
```

## Restricción del formato

No se debe confiar solo en el prompt.

La restricción debe venir de:
- `output.format: json`
- `output.schema`

El flujo esperado del executor sería:

1. tomar el `CurrentStep` ya renderizado
2. llamar al LLM con `system` + `prompt`
3. parsear JSON
4. validar contra `schema`
5. si es válido, guardar resultado
6. si hay `next`, mover `current` a ese `step_id`
7. si no es válido, fallar el step con error explícito

## Use case

Responsabilidad actual:
- ejecutar el step `llm_prompt`
- validar JSON contra schema
- guardar el resultado en `context.results[step_id]`
- emitir `LLM_PROMPT_RESULT`
- emitir `LLM_PROMPT_ERROR` cuando haga falta
- avanzar `current` con `next` o completar el run si no existe

## Steps complementarios

### `assign`

`assign` ya existe como mapper puro para limpiar o derivar valores del resultado del LLM.

Ejemplo:

```yaml
- id: assign_decision
  type: assign
  values:
    next_action: "{{results.analyze_issue.next_action}}"
    severity: "{{results.analyze_issue.severity}}"
```

### `if`

`if` sirve para ramificar en función del resultado del LLM.

Ejemplo:

```yaml
- id: check_decision
  type: if
  condition: "{{results.assign_decision.next_action}} == retry"
```

## Dirección recomendada

Secuencia recomendada a partir del estado actual:

1. usar `llm_prompt` para producir salida estructurada
2. usar `assign` para normalizar o simplificar resultados
3. introducir `if` para ramificar sin convertir `llm_prompt` en un step con lógica interna

La idea sigue siendo evitar una familia grande de steps LLM (`extract`, `classify`, `summarize`, etc.) antes de validar bien un contrato simple y fuerte.
