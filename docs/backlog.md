# Backlog

## LLM / siguiente iteracion

### v1
1. Steps complementarios
- introducir `if` para ramificar según el resultado del LLM o de steps previos
- bloqueado por la decision de modelo de control de flujo del runtime
- hay que decidir si `Skiller` sigue con flujo lineal por indice o evoluciona hacia transiciones explicitas entre steps
- ver spike: `docs/spike/if-control-flow.md`

2. Casos de uso reales y documentación
- documentar ejemplos de clasificación, extracción, resumen y decisión usando `llm_prompt`
- revisar y ampliar `docs/steps/llm_prompt.md`
- validar el diseño contra un caso de agente tipo `skill-mini-cline`

3. Robustez del parseo LLM
- decidir si conviene soportar más variantes de salida además de fenced JSON
- definir hasta dónde tolerar texto adicional alrededor del JSON antes de considerar que el contrato ha fallado

4. Política de proveedor y modelo
- decidir si `MiniMax-M2.5` sigue como opción principal para `llm_prompt`
- revisar si conviene ofrecer un modo con salida JSON estricta cuando el proveedor lo soporte

## Runtime / `current + start/next`

### Estado actual
1. Steps ya migrados
- `current` ya es el unico puntero persistido por `step_id`
- `GetStartStepUseCase` ya fija `current = start`
- `RenderCurrentStepUseCase` ya resuelve el step actual por `current`
- `notify`, `assign`, `llm_prompt`, `mcp` y `wait_webhook` ya usan el contrato común `NEXT | COMPLETED | WAITING`

2. Limpieza restante
- revisar nombres legacy del renderer y DTOs si sigue haciendo falta más limpieza

## Webhooks / wait_webhook

### v0
1. Resolver claves duplicadas `webhook + key`
- decidir si `webhook + key` debe identificar una unica espera activa
- definir que pasa si llega otro run con la misma clave
- ahora mismo el modelo todavia permite multiples coincidencias

### v1
2. Manejo de errores y observabilidad
- logs claros de webhook recibido, match, no match, resume y fallo
- mensajes utiles cuando no se puede reanudar un run

3. Tests por capas
- unit para matching y persistencia
- endurecer integration para `webhook -> resume`

4. Contrato operativo visible
- documentar limites del flujo actual del proceso `webhooks`
- documentar como se levanta y opera el proceso `webhooks`

### Hardening
5. Robustez bajo reinicios
- soportar reinicio de `Skiller`
- soportar maquina apagada y vuelta a arrancar
- asegurar que los runs en `WAITING` siguen siendo reanudables

6. Evitar dobles reanudaciones
- evitar dos `resume` sobre el mismo `run_id`
- endurecer locking y reentrada si hace falta

7. Politica operativa
- decidir timeouts y retries donde apliquen
- definir que significa "listo para produccion" para `wait_webhook`

## MCP hacia produccion

Estado actual:
- `notify` ya tiene un camino estable y e2e por CLI
- `mcp` ya funciona por YAML
- hay ejemplos minimos y tests para `notify`, `stdio` y `streamable-http`
- los e2e actuales entran por CLI real
- `notify` y `stdio local-mcp` ya tienen e2e por CLI
- `http_mcp_test` sigue cubierto en integracion, no como e2e
- el e2e `stdio local-mcp` debe mantenerse opt-in por configuracion externa, sin paths hardcodeados del autor

### Imprescindible
1. End-to-end reales estables
- endurecer los e2e reales para que sean fiables en automatizacion y CI
- decidir si `http mcp` tendra e2e real o seguira solo en integracion

2. Manejo de errores mas fuerte
- clasificar mejor errores de conexion, timeout, tool no encontrado y payload invalido
- devolver mensajes mas utiles para operacion

3. Timeouts y reintentos
- definir timeouts por operacion MCP
- decidir si hay retries y en que errores aplican

4. Observabilidad
- mejorar eventos y logs para diagnosticar fallos MCP rapido
- dejar claro servidor, transport, endpoint, tool y error final

### Importante
5. Contrato operativo
- documentar limites del runtime actual

6. Robustez del runtime
- revisar comportamiento bajo fallos parciales
- revisar ejecucion concurrente y reentrada del loop si eso va a existir en produccion

7. Persistencia y operacion
- decidir si SQLite es suficiente para el contexto real de uso o solo para esta etapa
- no invertir en migraciones por ahora; si cambia el esquema, se resetea la DB

### Opcional
8. Politica de despliegue
- definir que significa exactamente "listo para pro"
- acordar checklist de release para cambios en MCP

## DONE

### wait_webhook v0 base
- `wait_webhook` ya entra en `WAITING`
- `waits` y `webhook_events` ya se persisten
- la correlacion minima actual es `webhook + key`
- `resume <run_id>` ya existe
- `webhook receive` ya despierta el run y reentra en el loop
- ya hay integration y e2e CLI del flujo `wait_webhook`

### proceso webhooks minimo
- ya existe `src/skiller/tools/webhooks/`
- expone `GET /health` y `POST /webhooks/{webhook}/{key}`
- delega en `skiller webhook receive ...`
- `skiller run ... --start-webhooks` ya puede arrancarlo cuando el run queda en `WAITING`
- ya hay e2e real de `run --start-webhooks` + `POST /webhooks/...`

### registro de webhooks por canal
- ya existe `skiller webhook register <webhook>`
- el secreto se guarda por webhook en DB, no como secreto global
- el secreto se muestra solo una vez al registrar
- ya existe `skiller webhook remove <webhook>`
- el proceso `webhooks` ya valida firma leyendo el registro del `webhook`

### llm_prompt v0
- `llm_prompt` ya existe como step canónico
- el step completo ya sigue el patrón actual de renderizado
- la salida actual ya está restringida a `json`
- `output.format: json` y `output.schema` ya forman parte del contrato
- la salida del modelo ya se valida contra schema antes de persistir resultados
- ya existe `ExecuteLlmPromptStepUseCase`
- el resultado ya se guarda en `context.results[step_id]`
- el step ya falla con error claro si el modelo no devuelve JSON válido o no cumple el schema
- ya existe proveedor real `MiniMax`
- ya existe `FakeLLM` para tests deterministas
- ya hay integración y e2e real opt-in para `llm_prompt`
- ya existe observabilidad específica con `LLM_PROMPT_RESULT` y `LLM_PROMPT_ERROR`
- `skiller run ... --logs` ya puede devolver los eventos del run al terminar

### assign v0
- `assign` ya existe como mapper puro
- el step ya renderiza `values` con el contexto actual del run
- el renderizado ya conserva el tipo real cuando `values` usa un placeholder completo como `{{results.foo}}`
- `values` ya es obligatorio, debe ser objeto y no puede estar vacío
- el resultado ya se guarda en `context.results[step_id]`
- ya existe `ExecuteAssignStepUseCase`
- ya existe persistencia y reconstrucción desde `ASSIGN_RESULT`
- ya hay integración y e2e CLI para `assign`
