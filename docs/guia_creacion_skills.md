# Guia de Creacion de Skills

## Objetivo
Definir el formato YAML canonico de una skill y las reglas minimas para que el runtime actual la pueda ejecutar.

## Runtime actual
En esta fase del refactor, el camino canonico del loop nuevo ya deja activos `notify`, `assign`, `llm_prompt`, `mcp` y `wait_webhook`.

Otros `type` existentes siguen formando parte del repo, pero su integracion en el loop se esta migrando al modelo `current + start/next`.

Hoy existen estos `type`:

- `assign`
- `notify`
- `llm_prompt`
- `mcp`
- `wait_webhook`

Si una skill usa otros `type`, hoy no forma parte del camino canonico de ejecucion.

## Ubicacion y formato
- Carpeta: `skills/`
- Extension recomendada: `.yaml`
- `name` debe coincidir con el nombre del archivo

## Carga de skills
Hay dos modos de ejecutar una skill:

- `internal`: por nombre desde `skills/`
- `file`: por path explicito a un `.yaml` o `.json`

Ejemplos:

```bash
skiller run notify_test
skiller run --file /ruta/a/mi_skill.yaml
```

Al crear un run, la skill queda congelada en un snapshot dentro de la DB.
Si el YAML cambia despues, solo afecta a runs nuevos.

## Estructura minima

## Reglas actuales del flujo

- el step inicial debe tener `id: start`
- `GetStartStepUseCase` fija `run.current` apuntando a `start`
- en el camino ya migrado, cada step decide la transicion siguiente
- para `notify`, `assign`, `llm_prompt`, `mcp` y `wait_webhook`, `next` es opcional
- si uno de esos steps no tiene `next`, el run termina al resolverse

### Skill con `assign`
```yaml
name: assign_demo
description: "Test minimo con assign"
version: "0.1"

inputs:
  issue: string

steps:
  - id: start
    type: assign
    values:
      action: retry
      summary: "{{inputs.issue}}"
    next: done

  - id: done
    type: notify
    message: "{{results.start.action}}"
```

### Skill con `llm_prompt`
```yaml
name: llm_prompt_test
description: "Test minimo llm_prompt"
version: "0.1"

inputs:
  issue: string

steps:
  - id: start
    type: llm_prompt
    prompt: |
      Analyze this issue:
      {{inputs.issue}}
    next: done
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

  - id: done
    type: notify
    message: "{{results.start.next_action}}"
```

### Skill con `notify`
```yaml
name: notify_test
description: "Test minimo con un unico step notify"
version: "0.1"

inputs: {}

steps:
  - id: start
    type: notify
    message: "notify smoke ok"
```

### Skill con `notify` y `next`
```yaml
name: notify_chain
description: "Dos notify enlazados"
version: "0.1"

inputs: {}

steps:
  - id: start
    type: notify
    message: "first"
    next: done

  - id: done
    type: notify
    message: "second"
```

### Skill con `mcp`
```yaml
name: stdio_mcp_test
description: "Test minimo MCP via stdio"
version: "0.1"

inputs:
  file_path: string
  content: string

mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py
    cwd: /opt/local-mcp

steps:
  - id: start
    type: mcp
    mcp: local-mcp
    tool: files_action
    args:
      action: create
      path: "{{inputs.file_path}}"
      content: "{{inputs.content}}"
    next: done

  - id: done
    type: notify
    message: "created"
```

### Skill con `wait_webhook`
```yaml
name: wait_webhook_test
description: "Test minimo wait_webhook"
version: "0.1"

inputs:
  key: string

steps:
  - id: start
    type: wait_webhook
    webhook: test
    key: "{{inputs.key}}"
    next: done

  - id: done
    type: notify
    message: "resumed from webhook"
```

## Reglas del bloque `mcp`
Cada servidor MCP declarado en `mcp:` debe tener:

- `name`
- `transport`

Segun el `transport`:

- `stdio` requiere `command`
- `http` o `streamable-http` requiere `url`

Campos opcionales:

- `args`
- `cwd`
- `env`

## Renderizado
La configuracion MCP tambien se renderiza con el contexto del run.

Ejemplo valido:

```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/local-mcp/.venv/bin/python
    args:
      - /opt/local-mcp/local_mcp.py
```

Si una plantilla queda sin resolver, la configuracion MCP es invalida.

Nota:
Si el servidor MCP expone herramientas de filesystem, no asumas que sus roots se pueden controlar desde `mcp.env`.
En `local_mcp.py`, `FILES_ALLOWED_ROOTS` es configuracion propia del servidor y puede ignorar overrides del cliente.

## Casos validos

### `assign`
```yaml
steps:
  - id: start
    type: assign
    values:
      action: retry
      summary: "{{inputs.issue}}"
    next: done
```

### `llm_prompt`
```yaml
steps:
  - id: start
    type: llm_prompt
    prompt: "{{inputs.issue}}"
    next: done
    output:
      format: json
      schema:
        type: object
        required: [summary]
        properties:
          summary:
            type: string
```

### `notify`
```yaml
steps:
  - id: start
    type: notify
    message: "ok"
```

### `mcp` con `stdio`
```yaml
mcp:
  - name: local-mcp
    transport: stdio
    command: /opt/mcp/python

steps:
  - id: start
    type: mcp
    mcp: local-mcp
    tool: files_action
    next: done
```

### `mcp` con `streamable-http`
```yaml
inputs:
  mcp_url: string

mcp:
  - name: test-mcp
    transport: streamable-http
    url: "{{inputs.mcp_url}}"

steps:
  - id: start
    type: mcp
    mcp: test-mcp
    tool: ping
    next: done
```

### `wait_webhook` con `webhook + key`
```yaml
steps:
  - id: wait_merge
    type: wait_webhook
    webhook: github-pr-merged
    key: "{{results.create_pr.pr}}"
```

## Casos invalidos

### Servidor MCP no declarado
```yaml
steps:
  - id: create_file
    type: mcp
    mcp: local-mcp
    tool: files_action
```

Motivo: el step usa `local-mcp`, pero `mcp:` no lo declara.

### `stdio` sin `command`
```yaml
mcp:
  - name: local-mcp
    transport: stdio
```

Motivo: `stdio` requiere `command`.

### `streamable-http` sin `url`
```yaml
mcp:
  - name: test-mcp
    transport: streamable-http
```

Motivo: `http` y `streamable-http` requieren `url`.

### Template sin resolver
```yaml
inputs:
  python_bin: string

mcp:
  - name: local-mcp
    transport: stdio
    command: "{{inputs.python_bin}}"
```

Motivo: si `inputs.python_bin` no existe, la config MCP queda invalida.

### `wait_webhook` sin `webhook`
```yaml
steps:
  - id: wait_merge
    type: wait_webhook
    key: "42"
```

Motivo: `wait_webhook` requiere `webhook`.

### `wait_webhook` sin `key`
```yaml
steps:
  - id: wait_merge
    type: wait_webhook
    webhook: github-pr-merged
```

Motivo: `wait_webhook` requiere `key`.

### `assign` sin `values`
```yaml
steps:
  - id: prepare
    type: assign
```

Motivo: `assign` requiere `values`.

### `assign` con `values` vacío
```yaml
steps:
  - id: prepare
    type: assign
    values: {}
```

Motivo: `assign` requiere un objeto `values` no vacío.

## Checklist rapido
1. La skill vive en `skills/<nombre>.yaml`.
2. `name` coincide con el nombre del archivo.
3. Cada step tiene `id` unico.
4. Cada step usa un `type` soportado por el runtime actual: `assign`, `notify`, `llm_prompt`, `mcp` o `wait_webhook`.
5. Si un step usa `type: mcp`, el servidor existe en `mcp:`.
6. Si un step usa `type: wait_webhook`, declara `webhook` y `key`.
7. El bloque `mcp:` declara `transport` y los campos obligatorios para ese transport.
8. Los placeholders `{{inputs.x}}` o `{{results.x}}` existen y se resuelven.
