#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

read_agent_var() {
  local key="$1"
  python3 - "${key}" <<'PY'
import os
import sys
from pathlib import Path

key = sys.argv[1]
value = os.getenv(key)
if value is not None:
    print(value)
    raise SystemExit(0)

dotenv_path = Path(".env")
if not dotenv_path.exists():
    raise SystemExit(0)

for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        continue

    env_key, env_value = line.split("=", 1)
    if env_key.strip() != key:
        continue

    normalized = env_value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1]
    print(normalized)
    raise SystemExit(0)
PY
}

llm_provider="${AGENT_LLM_PROVIDER:-$(read_agent_var AGENT_LLM_PROVIDER)}"
minimax_api_key="${AGENT_MINIMAX_API_KEY:-$(read_agent_var AGENT_MINIMAX_API_KEY)}"

if [[ "${llm_provider}" != "minimax" ]]; then
  python3 -c 'import json; print(json.dumps({"status": "SKIPPED", "reason": "AGENT_LLM_PROVIDER is not minimax"}, indent=2))'
  exit 0
fi

if [[ -z "${minimax_api_key}" ]]; then
  python3 -c 'import json; print(json.dumps({"status": "SKIPPED", "reason": "missing AGENT_MINIMAX_API_KEY"}, indent=2))'
  exit 0
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=src "${runtime_python}" -m skiller run \
  --file tests/e2e/skills/llm_prompt_cli_real_e2e.yaml \
  --arg 'issue=Temporary auth timeout while refreshing token' \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["run_id"], "status": payload["status"]}, indent=2))'
