# Componentes del sistema y cómo implementarlos

## 1) CLI (`agent`)
- Objetivo: iniciar runs, consultar estado/logs, inyectar webhooks, cancelar.
- Implementación:
  - Librería: `Typer` (o `argparse` si quieres cero dependencias).
  - Comandos: `run`, `status`, `logs`, `steer`, `cancel`, `webhook inject`.
  - Flujo: el CLI no ejecuta lógica de negocio; solo publica eventos y consulta SQLite.
- Contratos:
  - `agent run <skill> --arg k=v...`
  - `agent webhook inject <wait_key> --json '{"repo":"x"}'`
- Pruebas:
  - Tests de comandos con `CliRunner`.
  - Validación de argumentos y códigos de salida.

## 2) Webhook Receiver (FastAPI)
- Objetivo: recibir señales externas y convertirlas en eventos internos.
- Implementación:
  - Endpoint: `POST /webhooks/{key}`.
  - Validación JSON y firma HMAC (`X-Signature`) opcional pero recomendada.
  - Publicación de evento `WEBHOOK_RECEIVED` en cola interna.
- Contratos:
  - Input: `{key, payload, headers}`
  - Output: `202 Accepted` con `event_id`.
- Pruebas:
  - Unit tests de validación y firma.
  - Integration test con webhook real simulado.

## 3) Event Bus
- Objetivo: desacoplar entrada/salida y ejecución del runtime.
- Implementación:
  - `asyncio.Queue` con consumidor único del runtime.
  - Envoltorio `publish(event)` / `consume()`.
  - Persistencia opcional en tabla `events` para replay básico.
- Contratos:
  - Evento base: `{id, type, run_id?, payload, created_at}`.
- Pruebas:
  - Orden FIFO.
  - Comportamiento bajo ráfaga de eventos.

## 4) Runtime / Orchestrator
- Objetivo: ejecutar la máquina de estados de cada run.
- Implementación:
  - Estados: `CREATED`, `RUNNING`, `WAITING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.
  - Loop event-driven: procesa `START_RUN`, `WEBHOOK_RECEIVED`, `STEER`, `CANCEL`.
  - Regla: el runtime es el único que avanza pasos y cambia estado.
  - Lock por `run_id` (DB o in-memory) para evitar doble ejecución concurrente.
- Contratos:
  - API interna: `handle_event(event)`.
  - API interna: `resume_run(run_id)`.
- Pruebas:
  - Transiciones válidas/invalidas de estado.
  - Reanudación correcta desde `WAITING`.

## 5) Skill Runner (DSL)
- Objetivo: cargar y ejecutar skills declarativas.
- Implementación:
  - Parser YAML/JSON + validación con `pydantic`.
  - Renderizado de variables (`{{inputs.x}}`, `{{context.y}}`) con `jinja2` restringido.
  - Tipos de paso: `tool`, `wait_webhook`, `llm`, `notify`.
- Contratos:
  - `load_skill(name) -> SkillDefinition`
  - `execute_step(run, step) -> StepResult`
- Pruebas:
  - Parsing/validación.
  - Resolución de templates.
  - Errores de steps mal definidos.

## 6) Tool Router
- Objetivo: resolver nombre lógico de herramienta y ejecutar adaptador correcto.
- Implementación:
  - Registro de handlers por prefijo:
    - `mcp.*` -> `MCPClientTool`
    - `internal.*` -> internal tools.
  - Timeout, retries y normalización de errores.
- Contratos:
  - `call(tool_name: str, args: dict, run_ctx) -> dict`
- Pruebas:
  - Routing correcto por nombre.
  - Retries en errores transitorios.

## 7) MCP Client Tool
- Objetivo: puente genérico a herramientas MCP.
- Implementación:
  - Interfaz: `mcp.call(server, tool, args)`.
  - Mapeo opcional de alias (`mcp.git.create_pr` -> `server=git`, `tool=create_pr`).
  - Normalizar respuesta: `{ok, data, error, raw}`.
- Contratos:
  - Input: `server`, `tool`, `args`.
  - Output: objeto JSON serializable.
- Pruebas:
  - Mock de servidor MCP.
  - Manejo de timeout y errores de protocolo.

## 8) Internal Tools
- Objetivo: capacidades base del runtime sin depender de MCP externo.
- Implementación:
  - `wait_webhook(wait_key, match, expires_at?)`
  - `notify(message)`
  - `set_context(key, value)`
  - Todos escriben en DB y emiten evento de auditoría.
- Contratos:
  - APIs puras y deterministas para facilitar tests.
- Pruebas:
  - Creación/resolución de waits.
  - Actualización de `context`.

## 9) LLM Adapter
- Objetivo: desacoplar proveedor del modelo.
- Implementación:
  - Interfaz común:
    - `generate(messages, tools_schema=None, config=None) -> LLMResult`
  - Adaptadores concretos: OpenAI, Anthropic, local.
  - Sin tool-calling directo: solo salida textual/estructurada para runtime.
- Contratos:
  - Entrada/Salida neutral, sin tipos del vendor.
- Pruebas:
  - Mock adapter para tests unitarios.
  - Snapshot tests de prompts críticos.

## 10) Policy Gate
- Objetivo: control de seguridad y gobernanza.
- Implementación:
  - Reglas por skill: allowlist de tools, máximos de pasos, timeout total, redacción.
  - Modo confirmación humana opcional para acciones sensibles.
- Contratos:
  - `authorize(run, step) -> Allow|Deny|RequireConfirmation`
- Pruebas:
  - Denegación de herramientas fuera de allowlist.
  - Timeout y límites.

## 11) State Store (SQLite)
- Objetivo: persistencia de runs, waits y eventos.
- Implementación:
  - Tablas mínimas: `runs`, `waits`, `events`.
  - Índices recomendados:
    - `runs(status, updated_at)`
    - `waits(wait_key, status)`
    - `events(run_id, created_at)`
  - Operaciones en transacciones cortas.
- Contratos:
  - Repositorios: `RunRepo`, `WaitRepo`, `EventRepo`.
- Pruebas:
  - Migraciones.
  - Integridad de transacciones.

## 12) Logging y observabilidad
- Objetivo: depurar y operar el runtime.
- Implementación:
  - Logs estructurados JSON con `run_id`, `event_id`, `step_id`.
  - Métricas mínimas: runs activas, latencia por step, tasa de fallos.
  - Trazas opcionales con OpenTelemetry.
- Pruebas:
  - Presencia de campos obligatorios en logs.
  - Métricas emitidas en pasos exitosos/fallidos.

## 13) Scheduler/Workers (mínimo POC)
- Objetivo: procesar eventos y runs pendientes.
- Implementación:
  - Un worker async único para simplicidad.
  - Evolución: múltiples workers con locking por `run_id`.
- Pruebas:
  - No procesar dos veces el mismo evento.
  - Recuperación tras reinicio.

## 14) Manejo de errores y reintentos
- Objetivo: robustez operativa.
- Implementación:
  - Clasificación: transitorio vs permanente.
  - Retry con backoff para tools externas.
  - Dead-letter de eventos fallidos para inspección manual.
- Pruebas:
  - Backoff y límite de reintentos.
  - Transición a `FAILED` al agotar reintentos.

## 15) Seguridad mínima
- Objetivo: reducir riesgo desde el POC.
- Implementación:
  - Secretos por variables de entorno.
  - Firma de webhooks + ventana anti-replay.
  - Sanitización de payload/logs (redacción de tokens).
- Pruebas:
  - Rechazo de firmas inválidas.
  - Redacción de campos sensibles.

## Orden sugerido de implementación
0. Crear el proyecto base (estructura de carpetas, `pyproject.toml`, entorno virtual, dependencias y configuración inicial).
1. `State Store` + esquemas.
2. `Event Bus` + `Runtime`.
3. `Skill Runner` + `Internal Tools`.
4. `Tool Router` + `MCP Client Tool`.
5. `CLI`.
6. `Webhook Receiver`.
7. `Policy Gate` + observabilidad + hardening.

## Orden de ejecución end-to-end
0. Proyecto ya inicializado (estructura, configuración y servicios base levantados).
1. `CLI` (`agent run ...`) inicia el proceso.
2. `State Store (SQLite)` crea el run en `CREATED`.
3. `Event Bus` recibe `START_RUN`.
4. `Scheduler/Worker` consume el evento.
5. `Runtime/Orchestrator` cambia el run a `RUNNING`.
6. `Skill Runner` carga la skill y obtiene el siguiente step.
7. `Policy Gate` autoriza o bloquea el step.
8. `Tool Router` resuelve destino (`mcp.*`, `internal.*`, `llm`).
9. `MCP Client Tool` o `Internal Tools` o `LLM Adapter` ejecutan la acción.
10. `State Store` persiste resultado, contexto, evento y logs.
11. `Logging/Observabilidad` emite trazas y métricas del step.
12. `Runtime` avanza al siguiente step y repite el ciclo.
13. Si el step es `wait_webhook`: `Internal Tool wait_webhook` crea wait y el run pasa a `WAITING`.
14. `Webhook Receiver (FastAPI)` recibe el webhook externo.
15. `Seguridad` valida firma y protege contra replay.
16. `Event Bus` publica `WEBHOOK_RECEIVED`.
17. `Scheduler/Worker` consume y entrega al `Runtime`.
18. `Runtime` consulta waits en SQLite, hace matching y reanuda.
19. El ciclo se repite hasta `SUCCEEDED`, `FAILED` o `CANCELLED`.
20. `Manejo de errores/reintentos` actúa en fallos transitorios antes del fallo final.
