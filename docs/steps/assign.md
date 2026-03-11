# `assign`

## Objetivo

`assign` es un step de mapeo puro.

No llama a servicios externos, no decide ramas y no espera eventos.
Solo toma valores ya disponibles en el contexto del run y los guarda en:

```yaml
results.<step_id>
```

## Shape mínimo

```yaml
- id: prepare_issue
  type: assign
  values:
    action: "{{results.analyze_issue.next_action}}"
    summary: "{{results.analyze_issue.summary}}"
```

Resultado esperado:

```yaml
results.prepare_issue.action
results.prepare_issue.summary
```

## Uso recomendado

`assign` sirve para:

- renombrar campos
- aplanar estructuras incómodas
- preparar un objeto más claro para steps siguientes
- evitar repetir rutas largas como `results.algo.muy.profundo`

## Renderizado

`assign` sigue el renderizado normal del runtime:

- `RenderCurrentStepUseCase` renderiza el step completo
- cualquier string dentro de `values` es renderizable

Ejemplo:

```yaml
- id: prepare
  type: assign
  values:
    action: "{{results.analyze_issue.next_action}}"
    meta:
      severity: "{{results.analyze_issue.severity}}"
      source: "llm"
    tags:
      - triage
      - "{{results.analyze_issue.severity}}"
```

Si una entrada de `values` es un placeholder completo como `{{results.foo}}`, el renderer conserva el valor real cuando existe, en vez de convertirlo siempre a string.

## Restricciones v0

En esta versión:

- `values` es obligatorio
- `values` debe ser un objeto
- `values` no debe estar vacío

No hace:

- expresiones
- comparaciones
- funciones
- casts
- validación por schema propia

Si hace falta lógica, eso pertenece a `if` o a una versión futura más expresiva.

## Persistencia

`assign` guarda el resultado en:

```yaml
results.<step_id>
```

Y además emite el evento:

```text
ASSIGN_RESULT
```

con:

- `step`
- `result`
