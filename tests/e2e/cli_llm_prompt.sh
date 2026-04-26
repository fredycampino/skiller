#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

settings_output="$(
  PYTHONPATH=src "${runtime_python}" - <<'PY'
import json

from skiller.infrastructure.config.settings import get_settings

settings = get_settings()
print(
    json.dumps(
        {
            "llm_provider": settings.llm_provider,
            "has_minimax_api_key": bool(settings.minimax_api_key),
        }
    )
)
PY
)"

llm_provider="$(
  printf '%s\n' "${settings_output}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["llm_provider"])'
)"
has_minimax_api_key="$(
  printf '%s\n' "${settings_output}" \
  | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["has_minimax_api_key"]).lower())'
)"

if [[ "${llm_provider}" != "minimax" ]]; then
  python3 -c 'import json; print(json.dumps({"status": "SKIPPED", "reason": "AGENT_LLM_PROVIDER is not minimax"}, indent=2))'
  exit 0
fi

if [[ "${has_minimax_api_key}" != "true" ]]; then
  python3 -c 'import json; print(json.dumps({"status": "SKIPPED", "reason": "missing AGENT_MINIMAX_API_KEY"}, indent=2))'
  exit 0
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

export AGENT_DB_PATH="${tmpdir}/runtime.db"

PYTHONPATH=src "${runtime_python}" -m skiller run \
  --file tests/e2e/skills/llm_prompt_cli_real_e2e.yaml \
  --arg 'issue=Temporary auth timeout while refreshing token' \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["run_id"], "status": payload["status"]}, indent=2))'
