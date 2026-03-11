#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=src "${runtime_python}" -m skiller run \
  --file tests/e2e/skills/notify_cli_e2e.yaml \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["run_id"], "status": payload["status"]}, indent=2))'
