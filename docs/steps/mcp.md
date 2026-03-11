# `mcp`

## Objetivo

`mcp` ejecuta una tool de un servidor MCP declarado en la skill.

El step:

- renderiza sus argumentos con el contexto del run
- resuelve la configuracion del servidor MCP desde el bloque `mcp:`
- ejecuta la tool
- guarda el resultado en `results.<step_id>`
- decide si el run continua o termina

## Shape mínimo

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py

steps:
  - id: start
    type: mcp
    mcp: local-mcp
    tool: files_action
    args:
      action: create
      path: "{{inputs.file_path}}"
      content: "{{inputs.content}}"
```

## Shape con `next`

```yaml
mcp:
  - name: test-mcp
    transport: streamable-http
    url: "{{inputs.mcp_url}}"

steps:
  - id: start
    type: mcp
    mcp: test-mcp
    tool: ping
    args: {}
    next: done

  - id: done
    type: notify
    message: "pong"
```

## Renderizado

`mcp` sigue el patrón normal del runtime:

- `RenderCurrentStepUseCase` renderiza el step completo
- `RenderMcpConfigUseCase` renderiza la configuracion MCP declarada en la skill

Campos renderizables habituales:

- `args`
- `mcp[].url`
- `mcp[].command`
- `mcp[].args`
- `mcp[].cwd`
- `mcp[].env`

## Validaciones

En esta versión:

- el step debe declarar `mcp`
- el step debe declarar `tool`
- `tool` no puede venir con prefijo `mcp.<server>.`
- `args` debe ser un objeto
- el servidor debe existir en el bloque `mcp:`
- la configuracion MCP renderizada no puede dejar templates sin resolver

## Resultado

`mcp` guarda el resultado de la tool en:

```yaml
results.<step_id>
```

Ejemplo:

```json
{
  "ok": true,
  "path": "/tmp/demo.txt"
}
```

## Persistencia

Además del resultado en `context.results[step_id]`, `mcp` emite:

```text
MCP_RESULT
```

con:

- `step`
- `mcp`
- `tool`
- `result`

## Transición

En el loop nuevo:

- si el step tiene `next`, el runtime mueve `current` a ese `step_id`
- si el step no tiene `next`, el run se completa

