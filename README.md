# Agent Runtime POC

Scaffold inicial del proyecto para el runtime de agentes (CLI + webhooks + MCP + skills).

## Estructura

- `src/runtime`: código de aplicación.
- `skills`: skills declarativas YAML/JSON.
- `tests`: pruebas básicas.
- `docs`: documentación técnica y diseño.

## Documentación

- `docs/runtime_poc_design.md`
- `docs/system_block_diagram.md`
- `docs/componentes_implementacion.md`

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Inicializar DB
agent init-db

# Ejecutar skill de ejemplo
agent run create_release --arg repo=my-repo --arg base_branch=main --arg release_branch=release/v1 --arg pr_title='Release v1' --arg publish_target=prod

# Inyectar webhook para reanudar el run
agent webhook inject webhook.merge.xyz --json '{"repo":"my-repo","branch":"release/v1"}'
```

## Comandos disponibles

- `agent init-db`
- `agent run <skill> --arg key=value`
- `agent status <run_id>`
- `agent logs <run_id>`
- `agent webhook inject <wait_key> --json '{...}'`
