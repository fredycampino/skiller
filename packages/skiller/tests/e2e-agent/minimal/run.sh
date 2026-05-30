#!/usr/bin/env bash
set -euo pipefail

expected_date="${1:-2026-05-16}"

cd "$(dirname "$0")/../../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

export AGENT_DB_PATH="${tmpdir}/runtime.db"

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e-agent/minimal/agent.yaml \
    --arg "expected_date=${expected_date}"
)"

run_id="$(
  printf '%s\n' "${run_output}" \
  | python3 -c 'import json,sys; payload=json.load(sys.stdin); print(payload["run_id"])'
)"

logs_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller logs "${run_id}"
)"

python3 - "${expected_date}" "${run_output}" "${logs_output}" <<'PY'
import json
import sys

expected_date = sys.argv[1]
payload = json.loads(sys.argv[2])
logs = json.loads(sys.argv[3])
status = payload["status"]
run_id = payload["run_id"]

if status != "SUCCEEDED":
    raise SystemExit(f"Unexpected run status: {status}")

step_success_events = [
    event
    for event in logs
    if event.get("type") == "STEP_SUCCESS" and event.get("step_id") == "answer_date"
]
if not step_success_events:
    raise SystemExit("Missing STEP_SUCCESS event for answer_date")

output = step_success_events[-1]["payload"]["output"]
actual_text = output["text"]
actual_ref = output["text_ref"]
actual_data = output["value"]["data"]

if actual_text != expected_date:
    raise SystemExit(f"Unexpected agent output text: {actual_text}")

if actual_ref != "data.final":
    raise SystemExit(f"Unexpected agent output text_ref: {actual_ref}")

if actual_data["final"] != expected_date:
    raise SystemExit(f"Unexpected agent final text: {actual_data['final']}")

print(json.dumps({"run_id": run_id, "status": status}, indent=2))
PY
