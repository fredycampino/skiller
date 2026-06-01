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
    --file packages/skiller/tests/e2e/skills/notify_link_cli_e2e.yaml
)"

run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller status "${run_id}" \
| python3 -c '
import json
import sys

payload = json.load(sys.stdin)
assert payload["status"] == "WAITING", payload
assert payload["wait_type"] == "input", payload
'

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller logs "${run_id}" \
| python3 -c '
import json
import sys

events = json.load(sys.stdin)
notify_events = [
    event for event in events
    if event["type"] == "STEP_SUCCESS" and event["step_id"] == "auth_link"
]
assert len(notify_events) == 1, notify_events
value = notify_events[0]["payload"]["output"]["value"]
assert value["format"] == "markdown", value
action = value["action"]
assert action["type"] == "open_url", action
assert action["label"] == "Open authorization", action
assert action["message"] == "Continue authorization in the browser.", action
assert action["url"] == "https://www.google.com/", action
assert action["auto"] is True, action
'

done_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller action done \
    "${run_id}" \
    auth_link
)"

printf '%s\n' "${done_output}" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
assert payload["status"] == "DONE", payload
assert payload["done"] is True, payload
assert payload["changed"] is True, payload
'

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller logs "${run_id}" \
| python3 -c '
import json
import sys

events = json.load(sys.stdin)
action_done_events = [event for event in events if event["type"] == "ACTION_DONE"]
assert len(action_done_events) == 1, action_done_events
event = action_done_events[0]
assert event["step_id"] == "auth_link", event
assert event["step_type"] == "notify", event
assert event["payload"] == {"type": "open_url", "status": "done"}, event
'

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller input receive \
  "${run_id}" \
  --text "notify-link-ok" >/dev/null

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller resume \
  "${run_id}" >/dev/null

status_payload=""
for _ in {1..20}; do
  status_payload="$(
    PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller status \
      "${run_id}"
  )"
  if printf '%s\n' "${status_payload}" \
    | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin)["status"] == "SUCCEEDED" else 1)'
  then
    break
  fi
  sleep 0.1
done

printf '%s\n' "${status_payload}" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
assert payload["status"] == "SUCCEEDED", payload
print(json.dumps({
    "run_id": payload["run_id"],
    "status": payload["status"],
}, indent=2))
'
