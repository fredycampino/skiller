#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../../../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e/skills/run_end_action_cli_e2e.yaml
)"

run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller status "${run_id}" \
| python3 -c '
import json
import sys

payload = json.load(sys.stdin)
assert payload["status"] == "SUCCEEDED", payload
'

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller logs "${run_id}" \
| python3 -c '
import json
import sys

events = json.load(sys.stdin)
finished_events = [event for event in events if event["type"] == "RUN_FINISHED"]
assert len(finished_events) == 1, finished_events
event = finished_events[0]
assert event["step_id"] is None, event
assert event["step_type"] is None, event
assert event["payload"] == {
    "status": "SUCCEEDED",
    "action": {
        "type": "run",
        "label": "Open follow-up",
        "arg": "--file ./flows/followup.yaml",
        "params": "--val pepe",
        "auto": True,
    },
}, event
'

printf '%s\n' "${run_output}" \
| python3 -c 'import json,sys; payload=json.load(sys.stdin); print(json.dumps({"run_id": payload["run_id"], "status": payload["status"]}, indent=2))'
