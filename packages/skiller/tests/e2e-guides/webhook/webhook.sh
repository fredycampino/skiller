#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../../.."

tmpdir="$(mktemp -d)"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_WEBHOOKS_HOST="127.0.0.1"
export SKILLER_DEBUG_HOME="${tmpdir}/home"

cleanup() {
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller server stop >/dev/null 2>&1 || /usr/bin/printf ''
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

skiller() {
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller "$@"
}

start_output=""
base_port="${SKILLER_TEST_WEBHOOK_PORT:-18100}"
for attempt in {0..19}; do
  export AGENT_WEBHOOKS_PORT="$((base_port + attempt))"
  if start_output="$(skiller server start 2>/dev/null)"; then
    started="$(printf '%s\n' "${start_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["started"])')"
    if [[ "${started}" == "True" ]]; then
      break
    fi
  fi
  start_output=""
done
if [[ -z "${start_output}" ]]; then
  printf 'Unable to start server\n' >&2
  exit 1
fi
printf '%s\n' "${start_output}" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
assert payload["started"] is True
assert payload["running"] is True
'

registration="$(skiller webhook register provider-events --auth token --token-header X-Webhook-Token)"
secret="$(printf '%s\n' "${registration}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["secret"])')"

run_output="$(skiller run --file packages/skiller/tests/e2e-guides/webhook/webhook.yaml)"
run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
printf '%s\n' "${run_output}" | python3 -c '
import json, sys
assert json.load(sys.stdin)["status"] == "WAITING"
'

endpoint_base="${SKILLER_TEST_WEBHOOK_ENDPOINT:-http://${AGENT_WEBHOOKS_HOST}:${AGENT_WEBHOOKS_PORT}}"
endpoint="${endpoint_base%/}/webhooks/provider-events/inbox"
unauthorized_status="$(curl -sS -o "${tmpdir}/unauthorized.json" -w '%{http_code}' -X POST "${endpoint}" -H 'Content-Type: application/json' --data '{"message":"ignored"}')"
if [[ "${unauthorized_status}" != "401" ]]; then
  printf 'Expected unauthenticated request to return 401, got %s\n' "${unauthorized_status}" >&2
  exit 1
fi

curl -fsS -X POST "${endpoint}" \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Token: ${secret}" \
  --data '{"message":"Hello from a webhook"}' >/dev/null

for attempt in {1..50}; do
  status_output="$(skiller status "${run_id}")"
  status="$(printf '%s\n' "${status_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  if [[ "${status}" == "SUCCEEDED" ]]; then
    break
  fi
  sleep 0.1
done
if [[ "${status}" != "SUCCEEDED" ]]; then
  skiller logs "${run_id}" >&2
  printf 'Expected run to succeed, got: %s\n' "${status_output}" >&2
  exit 1
fi

skiller logs "${run_id}" | python3 -c '
import json, sys
logs = json.load(sys.stdin)
assert any(
    event["step_id"] == "show_event"
    and event["type"] == "STEP_SUCCESS"
    and event["payload"]["output"]["text"] == "Hello from a webhook"
    for event in logs
), logs
'

skiller webhook remove provider-events >/dev/null
printf '{\n  "run_id": "%s",\n  "status": "SUCCEEDED"\n}\n' "${run_id}"
