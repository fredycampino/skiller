# Feature Matrix

| Feature | Estado | Entry Point | Persistencia | Tests | Notas |
|---|---|---|---|---|---|
| `notify` | Operativo | `skiller run` | `runs`, `events` | unit, integration, e2e | Camino base estable |
| `assign` | Operativo | `skiller run` | `runs`, `events` | unit, integration, e2e | Mapper puro con resultado en `context.results[step_id]` |
| `switch` | Operativo | `skiller run` | `runs`, `events` | unit, integration, e2e | Routing por igualdad exacta sobre un valor |
| `when` | Operativo | `skiller run` | `runs`, `events` | unit, integration, e2e | Routing por condiciones ordenadas sobre un valor |
| `llm_prompt` | Operativo | `skiller run` | `runs`, `events` | unit, integration, e2e manual opt-in | Requiere proveedor LLM configurado |
| `mcp` | Operativo | `skiller run` | `runs`, `events` | unit, integration, e2e manual stdio | Usa config MCP desde YAML |
| `wait_webhook` | Operativo | `skiller run` | `runs`, `waits`, `webhook_events`, `webhook_receipts` | integration, e2e | Reanuda por `webhook + key` |
| Skill interna | Operativo | `skiller run <skill>` | `runs.skill_source=internal`, `skill_ref`, `skill_snapshot_json` | unit, integration, e2e | Carga desde `skills/` |
| Skill externa por archivo | Operativo | `skiller run --file ...` | `runs.skill_source=file`, `skill_ref`, `skill_snapshot_json` | integration, e2e | Usa snapshot del YAML al crear el run |
| Snapshot de skill | Operativo | `StartRunUseCase` | `runs.skill_snapshot_json` | integration | Evita releer el archivo durante el run |
| `resume` manual | Operativo | `skiller resume <run_id>` | `runs`, `events` | unit, integration | Reanuda solo runs en `WAITING` |
| `webhook receive` | Operativo | `skiller webhook receive ...` | `webhook_events`, `webhook_receipts`, `waits`, `events` | unit, integration | Deduplica y despierta runs |
| Proceso `webhooks` mínimo | Operativo | `python -m skiller.tools.webhooks` | Usa DB compartida | unit, e2e | `GET /health`, `POST /webhooks/{webhook}/{key}` |
| `--start-webhooks` | Operativo | `skiller run ... --start-webhooks` | No persiste lifecycle | unit, e2e | Arranca el proceso solo si el run queda en `WAITING` |
| Registro de webhooks por canal | Operativo | `skiller webhook register <webhook>` | `webhook_registrations` | unit, e2e | Devuelve secreto una sola vez |
| Borrado de webhook | Operativo | `skiller webhook remove <webhook>` | `webhook_registrations` | unit | No hay `rotate` todavía |
| Firma HMAC por canal | Operativo | `POST /webhooks/{webhook}/{key}` | Lee `webhook_registrations` | unit, e2e | Requiere `x-signature` válida |
| Duplicados `webhook + key` | Pendiente | `wait_webhook` / `webhook receive` | `waits` | pendiente | Falta cerrar política de unicidad |
| `http mcp` como e2e real | Parcial | `skiller run http_mcp_test` | `runs`, `events` | integration | Sigue fuera de la suite manual estable |
