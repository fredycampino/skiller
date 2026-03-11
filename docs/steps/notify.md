# `notify`

## Objetivo

`notify` es el step operativo más simple del runtime.

No llama a servicios externos ni transforma datos complejos.
Solo emite un mensaje, guarda su resultado en el contexto y decide si el run continúa o termina.

## Shape mínimo

```yaml
- id: start
  type: notify
  message: "notify smoke ok"
```

## Shape con `next`

```yaml
- id: start
  type: notify
  message: "first"
  next: done

- id: done
  type: notify
  message: "second"
```

## Renderizado

`notify` sigue el patrón normal del runtime:

- `RenderCurrentStepUseCase` renderiza el step completo
- `message` es renderizable

Placeholders esperados:

- `{{inputs...}}`
- `{{results...}}`

Ejemplo:

```yaml
- id: done
  type: notify
  message: "{{results.start.next_action}}"
```

## Resultado

`notify` guarda el resultado en:

```yaml
results.<step_id>
```

Con esta forma:

```json
{
  "ok": true,
  "message": "retry"
}
```

## Persistencia

Además del resultado en `context.results[step_id]`, `notify` emite:

```text
NOTIFY
```

con:

- `step`
- `message`

## Transición

En el loop nuevo:

- si el step tiene `next`, el runtime mueve `current` a ese `step_id`
- si el step no tiene `next`, el run se completa

## Restricciones

En esta versión:

- `message` se trata como string
- `next`, si existe, debe ser un `step_id` no vacío

