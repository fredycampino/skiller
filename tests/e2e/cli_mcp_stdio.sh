#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
content_text="${1:-hola-e2e}"
tmpdir="$(mktemp -d)"
output_file="${tmpdir}/stdio-mcp-e2e.txt"
trap 'rm -rf "${tmpdir}"' EXIT

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=src "${runtime_python}" -m skiller run \
  --file skills/stdio_mcp_test.yaml \
  --arg "file_path=${output_file}" \
  --arg "content=${content_text}" \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["run_id"], "status": payload["status"]}, indent=2))'
