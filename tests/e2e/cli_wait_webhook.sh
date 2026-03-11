#!/usr/bin/env bash
set -euo pipefail

webhook_key="${1:-$(date +%s%N)}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

run_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller run \
    --file tests/e2e/skills/wait_webhook_cli_e2e.yaml \
    --arg "key=${webhook_key}"
)"

run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

receive_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller webhook receive \
    test \
    "${webhook_key}" \
    --json '{"ok": true}' \
    --dedup-key "delivery-${webhook_key}"
)"
_="${receive_output}"

PYTHONPATH=src "${runtime_python}" -m skiller status "${run_id}" \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["id"], "status": payload["status"]}, indent=2))'
