#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../../.."

tmpdir="$(mktemp -d)"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_WEBHOOKS_HOST="127.0.0.1"
# Keep the configured provider available to server-spawned workers.
unset SKILLER_DEBUG_HOME

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
base_port="${SKILLER_TEST_WEBHOOK_PORT:-18300}"
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

registration="$(skiller webhook register agent-wh --auth token --token-header X-Webhook-Token)"
secret="$(printf '%s\n' "${registration}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["secret"])')"

run_output="$(skiller run packages/skiller/tests/e2e-guides/agent-wh/agent-wh.yaml)"
run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
printf '%s\n' "${run_output}" | python3 -c '
import json, sys
assert json.load(sys.stdin)["status"] == "WAITING"
'

endpoint_base="${SKILLER_TEST_WEBHOOK_ENDPOINT:-http://${AGENT_WEBHOOKS_HOST}:${AGENT_WEBHOOKS_PORT}}"
endpoint="${endpoint_base%/}/webhooks/agent-wh/inbox"
unauthorized_status="$(curl --max-time 20 -sS -o "${tmpdir}/unauthorized.json" -w '%{http_code}' -X POST "${endpoint}" -H 'Content-Type: application/json' --data '{"message":"ignored"}')"
if [[ "${unauthorized_status}" != "401" ]]; then
  printf 'Expected unauthenticated request to return 401, got %s\n' "${unauthorized_status}" >&2
  exit 1
fi

curl --max-time 20 -fsS -X POST "${endpoint}" \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Token: ${secret}" \
  --data '{"message":"Hello! What can you help me with?"}' >/dev/null

for ((attempt = 0; attempt < ${SKILLER_TEST_AGENT_TIMEOUT:-120}; attempt++)); do
  skiller logs "${run_id}" >"${tmpdir}/logs.json"
  status_output="$(skiller status "${run_id}")"
  status="$(printf '%s\n' "${status_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  if [[ "${status}" == "FAILED" ]]; then
    cat "${tmpdir}/logs.json" >&2
    exit 1
  fi
  if [[ "${status}" == "WAITING" ]] && python3 -c '
import json, sys
logs = json.load(open(sys.argv[1]))
sys.exit(0 if any(e["type"] == "STEP_SUCCESS" and e["step_id"] == "respond" for e in logs) else 1)
' "${tmpdir}/logs.json"; then
    break
  fi
  sleep 1
done

python3 - "${tmpdir}/logs.json" <<'PYTHON'
import json, sys
logs = json.load(open(sys.argv[1]))
received = next(e for e in logs if e["type"] == "STEP_SUCCESS" and e["step_id"] == "wait_task")
assert received["payload"]["output"]["value"]["payload"]["message"] == "Hello! What can you help me with?"
reply = next(e for e in logs if e["type"] == "AGENT_FINAL_ASSISTANT_MESSAGE")
assert reply["payload"]["text"].strip()
completed = next(e for e in logs if e["type"] == "STEP_SUCCESS" and e["step_id"] == "respond")
assert completed["payload"]["output"]["value"]["data"]["stop_reason"] == "final"
assert logs[-1]["type"] == "RUN_WAITING" and logs[-1]["step_id"] == "wait_task"
print(reply["payload"]["text"])
PYTHON

skiller delete "${run_id}" >/dev/null
skiller webhook remove agent-wh >/dev/null
printf '{\n  "run_id": "%s",\n  "status": "WAITING"\n}\n' "${run_id}"
