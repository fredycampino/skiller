# Skiller Runtime POC

Runtime experimental de skills con soporte actual para:
- `notify`
- `llm_prompt`
- `mcp`
- `wait_webhook`

## Estructura

- `src/skiller`: código de aplicación.
- `skills`: skills declarativas YAML/JSON.
- `tests`: pruebas básicas.
- `docs`: documentación técnica y diseño.

## Documentación

- `docs/system_block_diagram.md`
- `docs/reglas_arquitectura.md`
- `docs/catalogo_use_cases.md`
- `docs/backlog.md`
- `docs/guia_creacion_skills.md`
- `docs/skiller_webhooks_functional_overview.md`

## Quickstart

Comando recomendado: `skiller`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Skill interna minima
skiller run notify_test

# Skill con llm_prompt usando MiniMax
AGENT_LLM_PROVIDER=minimax \
AGENT_MINIMAX_API_KEY=tu_api_key \
AGENT_MINIMAX_MODEL=MiniMax-M2.5 \
skiller run --file tests/e2e/skills/llm_prompt_cli_real_e2e.yaml --arg issue="Traceback auth failed"

# E2E manuales por step
./tests/e2e/cli_notify.sh
./tests/e2e/cli_assign.sh "dependency timeout"
./tests/e2e/cli_llm_prompt.sh
./tests/e2e/cli_mcp_stdio.sh "hola-e2e"
./tests/e2e/cli_wait_webhook.sh 42
./tests/e2e/cli_all.sh

# Skill externa por archivo
skiller run --file skills/notify_test.yaml

# Estado y logs
skiller status <run_id>
skiller logs <run_id>

# Reanudar un run en WAITING
skiller resume <run_id>

# Inyectar webhook para wait_webhook
skiller webhook receive github-pr-merged 42 --json '{"merged": true}' --dedup-key delivery-123

# Arrancar el proceso webhooks al dejar un run en WAITING
skiller run --file tests/e2e/skills/wait_webhook_cli_e2e.yaml --arg key=42 --start-webhooks

# Registrar y borrar un canal webhook
skiller webhook register github-ci
skiller webhook remove github-ci
```

## Skills actuales

- `skills/notify_test.yaml`
- `skills/stdio_mcp_test.yaml`
- `skills/http_mcp_test.yaml`

## MCP

La fuente de verdad de la conexión MCP vive en el YAML de la skill, dentro del bloque `mcp:`.

Ejemplos mínimos:
- `stdio` en `skills/stdio_mcp_test.yaml`
- `streamable-http` en `skills/http_mcp_test.yaml`

## Comandos disponibles

- `skiller init-db`
- `skiller run <skill> --arg key=value`
- `skiller run --file /ruta/skill.yaml --arg key=value`
- `skiller run ... --start-webhooks`
- `skiller resume <run_id>`
- `skiller status <run_id>`
- `skiller logs <run_id>`
- `skiller webhook register <webhook>`
- `skiller webhook remove <webhook>`
- `skiller webhook receive <webhook> <key> --json '{...}' --dedup-key <key>`
- `python -m skiller.tools.webhooks`

## CLI Manuales E2E

Los flujos manuales de e2e viven en `tests/e2e/cli_*.sh`.

- `cli_notify.sh`
- `cli_assign.sh`
- `cli_llm_prompt.sh`
- `cli_mcp_stdio.sh`
- `cli_wait_webhook.sh`
- `cli_all.sh`

Cada `cli_*.sh` usa una DB temporal aislada y la limpia al terminar para no dejar basura en el entorno.
Intentan hacer solo lo minimo: lanzar los comandos reales de `skiller` y devolver un JSON corto con `run_id` y `status`.
`cli_all.sh` consume esa salida y muestra un resumen corto `PASS/SKIP/FAIL`.

`cli_mcp_stdio.sh` valida el step `mcp` por `stdio` con una fixture interna del repo.
No usa la configuracion `AGENT_MCP_LOCAL_MCP_*` ni permite controlar roots desde el cliente.
Si pruebas contra `local_mcp.py` real, los roots de `files_action` se resuelven del servidor MCP y no de variables inyectadas por `skiller`.

Los `test_*_e2e.py` se retiraron para no mezclar en `pytest` casos manuales u opt-in que no forman parte de una suite automatizada estable.
