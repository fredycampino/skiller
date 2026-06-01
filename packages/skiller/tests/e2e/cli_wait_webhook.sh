#!/usr/bin/env bash
set -euo pipefail

webhook_key="${1:-$(date +%s%N)}"
tmpdir="$(mktemp -d)"

cd "$(dirname "$0")/../../../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_WEBHOOKS_HOST="127.0.0.1"
export AGENT_WEBHOOKS_PORT="${SKILLER_TEST_WEBHOOK_PORT:-18082}"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

cleanup() {
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller server stop >/dev/null 2>&1 || true
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller server start >/dev/null

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e/skills/wait_webhook_cli_e2e.yaml \
    --arg "key=${webhook_key}"
)"

run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

receive_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller webhook receive \
    test \
    "${webhook_key}" \
    --json '{"ok": true}' \
    --dedup-key "delivery-${webhook_key}"
)"
_="${receive_output}"

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller status "${run_id}" \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["run_id"], "status": payload["status"]}, indent=2))'
