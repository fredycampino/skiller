#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_WEBHOOKS_HOST="127.0.0.1"
start_output=""
attempt=0
base_port="${SKILLER_TEST_WEBHOOK_PORT:-18081}"

while (( attempt < 20 )); do
  export AGENT_WEBHOOKS_PORT="$((base_port + attempt))"
  if start_output="$(PYTHONPATH=src "${runtime_python}" -m skiller server start 2>/dev/null)"; then
    break
  fi
  attempt=$((attempt + 1))
done

if [[ -z "${start_output}" ]]; then
  printf 'Unable to start server on any test port in range [%s, %s]\n' "${base_port}" "$((base_port + 19))" >&2
  exit 1
fi

start_status="$(
  printf '%s\n' "${start_output}" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["started"]).lower())'
)"
start_endpoint="$(
  printf '%s\n' "${start_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["endpoint"])'
)"

if [[ "${start_status}" != "true" && "${start_status}" != "false" ]]; then
  printf 'Unexpected start payload: %s\n' "${start_output}" >&2
  exit 1
fi

status_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller server status
)"

running_status="$(
  printf '%s\n' "${status_output}" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["running"]).lower())'
)"
status_endpoint="$(
  printf '%s\n' "${status_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["endpoint"])'
)"

if [[ "${running_status}" != "true" ]]; then
  printf 'Expected running=true, got: %s\n' "${status_output}" >&2
  exit 1
fi

if [[ "${start_endpoint}" != "${status_endpoint}" ]]; then
  printf 'Endpoint mismatch start=%s status=%s\n' "${start_endpoint}" "${status_endpoint}" >&2
  exit 1
fi

stop_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller server stop
)"

stopped_status="$(
  printf '%s\n' "${stop_output}" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["stopped"]).lower())'
)"

if [[ "${stopped_status}" != "true" ]]; then
  printf 'Expected stopped=true, got: %s\n' "${stop_output}" >&2
  exit 1
fi

final_status_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller server status
)"

final_running="$(
  printf '%s\n' "${final_status_output}" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["running"]).lower())'
)"

if [[ "${final_running}" != "false" ]]; then
  printf 'Expected running=false after stop, got: %s\n' "${final_status_output}" >&2
  exit 1
fi

python3 - <<'PY'
import json

print(json.dumps({"run_id": "server", "status": "SUCCEEDED"}, indent=2))
PY
