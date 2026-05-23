#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

export AGENT_DB_PATH="${tmpdir}/runtime.db"

run_case() {
  local yaml_path="$1"
  local mode="$2"
  local step_id="$3"
  local expected_tool_calls="$4"
  local label
  label="$(basename "${yaml_path}")"

  echo "==> ${label}"

  local run_output
  run_output="$(
    PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
      --file "${yaml_path}"
  )"

  local run_id
  run_id="$(
    printf '%s\n' "${run_output}" \
    | python3 -c 'import json,sys; payload=json.load(sys.stdin); print(payload["run_id"])'
  )"

  local logs_output
  logs_output="$(
    PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller logs "${run_id}"
  )"

  python3 - "${run_output}" "${logs_output}" "${mode}" "${step_id}" "${expected_tool_calls}" "${label}" <<'PY'
import json
import sys

run_payload = json.loads(sys.argv[1])
logs = json.loads(sys.argv[2])
mode = sys.argv[3]
step_id = sys.argv[4]
expected_tool_calls = int(sys.argv[5])
label = sys.argv[6]

run_id = run_payload["run_id"]
status = run_payload["status"]

if status != "SUCCEEDED":
    raise SystemExit(f"Unexpected run status: {status}")

tool_call_events = [
    event
    for event in logs
    if event.get("type") == "AGENT_TOOL_CALL" and event.get("step_id") == step_id
]
if len(tool_call_events) != expected_tool_calls:
    raise SystemExit(f"Expected {expected_tool_calls} shell tool calls, got {len(tool_call_events)}")

for event in tool_call_events:
    payload = event["payload"]
    if payload["tool"] != "shell":
        raise SystemExit(f"Unexpected tool: {payload['tool']}")
    if payload["args"]["command"] != "pwd":
        raise SystemExit(f"Unexpected shell command: {payload['args']['command']}")

tool_result_events = [
    event
    for event in logs
    if event.get("type") == "AGENT_TOOL_RESULT" and event.get("step_id") == step_id
]
if len(tool_result_events) != expected_tool_calls:
    raise SystemExit(f"Expected {expected_tool_calls} shell tool results, got {len(tool_result_events)}")

for event in tool_result_events:
    payload = event["payload"]
    if payload["tool"] != "shell":
        raise SystemExit(f"Unexpected result tool: {payload['tool']}")
    if payload["status"] != "COMPLETED":
        raise SystemExit(f"Unexpected shell result status: {payload['status']}")
    if payload["data"]["exit_code"] != 0:
        raise SystemExit(f"Unexpected shell exit code: {payload['data']['exit_code']}")

step_success_events = [
    event
    for event in logs
    if event.get("type") == "STEP_SUCCESS" and event.get("step_id") == step_id
]
if not step_success_events:
    raise SystemExit(f"Missing STEP_SUCCESS event for {step_id}")

output = step_success_events[-1]["payload"]["output"]
data = output["value"]["data"]
if data["tool_call_count"] != expected_tool_calls:
    raise SystemExit(f"Unexpected persisted tool_call_count: {data['tool_call_count']}")

if mode == "final":
    if output["text"] != "done":
        raise SystemExit(f"Expected final text done, got: {output['text']}")
    if data["stop_reason"] != "final":
        raise SystemExit(f"Unexpected stop reason: {data['stop_reason']}")

if mode == "max-turns":
    if output["text"] != "":
        raise SystemExit(f"Expected empty final text, got: {output['text']}")
    if data["stop_reason"] != "max_turns_exhausted":
        raise SystemExit(f"Unexpected stop reason: {data['stop_reason']}")
    max_turn_events = [
        event
        for event in logs
        if event.get("type") == "AGENT_MAX_TURNS_EXHAUSTED" and event.get("step_id") == step_id
    ]
    if not max_turn_events:
        raise SystemExit(f"Missing AGENT_MAX_TURNS_EXHAUSTED for {step_id}")

print(f"[PASS] {label} {run_id}")
PY
}

run_case \
  "packages/skiller/tests/e2e-agent/tools-calls/max-turn.yaml" \
  "final" \
  "shell_once" \
  1

echo
run_case \
  "packages/skiller/tests/e2e-agent/tools-calls/fail-max-turn.yaml" \
  "max-turns" \
  "shell_once_no_final" \
  1

echo
run_case \
  "packages/skiller/tests/e2e-agent/tools-calls/multi-tools.yaml" \
  "final" \
  "shell_three_times" \
  3

echo
run_case \
  "packages/skiller/tests/e2e-agent/tools-calls/fail-multi-tools.yaml" \
  "max-turns" \
  "shell_three_times_short" \
  2

python3 - <<'PY'
import json

print(json.dumps({"run_id": "tools-calls", "status": "SUCCEEDED"}, indent=2))
PY
