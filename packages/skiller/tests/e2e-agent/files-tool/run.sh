#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
workspace="packages/skiller/tests/e2e-agent/files-tool/workspace"
file_path="${workspace}/notes.txt"

cleanup() {
  rm -f "${file_path}"
  rmdir "${workspace}" 2>/dev/null || true
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

mkdir -p "${workspace}"
expected_content="files e2e content"

export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_AGENT_CONFIG_FILE="packages/skiller/tests/e2e-agent/files-tool/agent.json"

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e-agent/files-tool/agent.yaml \
    --arg "file_path=${file_path}" \
    --arg "expected_content=${expected_content}"
)"

run_id="$(
  printf '%s\n' "${run_output}" \
  | python3 -c 'import json,sys; payload=json.load(sys.stdin); print(payload["run_id"])'
)"

logs_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller logs "${run_id}"
)"

python3 - "${run_output}" "${logs_output}" "${file_path}" "${expected_content}" <<'PY'
import json
import sys
from pathlib import Path

run_payload = json.loads(sys.argv[1])
logs = json.loads(sys.argv[2])
file_path = sys.argv[3]
expected_content = sys.argv[4]

run_id = run_payload["run_id"]
status = run_payload["status"]

if status != "SUCCEEDED":
    raise SystemExit(f"Unexpected run status: {status}")

tool_call_events = [
    event
    for event in logs
    if event.get("type") == "AGENT_TOOL_CALL" and event.get("step_id") == "files_write_read"
]
if len(tool_call_events) != 2:
    raise SystemExit(f"Expected 2 files tool calls, got {len(tool_call_events)}")

write_call = tool_call_events[0]["payload"]
if write_call["tool"] != "files":
    raise SystemExit(f"Unexpected first tool: {write_call['tool']}")
if write_call["args"]["action"] != "write":
    raise SystemExit(f"Unexpected first files action: {write_call['args']['action']}")
if write_call["args"]["path"] != file_path:
    raise SystemExit(f"Unexpected write path: {write_call['args']['path']}")
if write_call["args"]["write_text"] != expected_content:
    raise SystemExit(f"Unexpected write text: {write_call['args']['write_text']}")

read_call = tool_call_events[1]["payload"]
if read_call["tool"] != "files":
    raise SystemExit(f"Unexpected second tool: {read_call['tool']}")
if read_call["args"]["action"] != "read":
    raise SystemExit(f"Unexpected second files action: {read_call['args']['action']}")
if read_call["args"]["path"] != file_path:
    raise SystemExit(f"Unexpected read path: {read_call['args']['path']}")

tool_result_events = [
    event
    for event in logs
    if event.get("type") == "AGENT_TOOL_RESULT" and event.get("step_id") == "files_write_read"
]
if len(tool_result_events) != 2:
    raise SystemExit(f"Expected 2 files tool results, got {len(tool_result_events)}")

write_result = tool_result_events[0]["payload"]
if write_result["tool"] != "files":
    raise SystemExit(f"Unexpected first result tool: {write_result['tool']}")
if write_result["status"] != "COMPLETED":
    raise SystemExit(f"Unexpected write result status: {write_result['status']}")
if write_result["data"]["action"] != "write":
    raise SystemExit(f"Unexpected write result action: {write_result['data']['action']}")

read_result = tool_result_events[1]["payload"]
if read_result["tool"] != "files":
    raise SystemExit(f"Unexpected second result tool: {read_result['tool']}")
if read_result["status"] != "COMPLETED":
    raise SystemExit(f"Unexpected read result status: {read_result['status']}")
if read_result["data"]["action"] != "read":
    raise SystemExit(f"Unexpected read result action: {read_result['data']['action']}")
if read_result["data"]["content"] != expected_content:
    raise SystemExit(f"Unexpected read content: {read_result['data']['content']}")

if Path(file_path).read_text(encoding="utf-8") != expected_content:
    raise SystemExit("File on disk does not contain expected content")

step_success_events = [
    event
    for event in logs
    if event.get("type") == "STEP_SUCCESS" and event.get("step_id") == "files_write_read"
]
if not step_success_events:
    raise SystemExit("Missing STEP_SUCCESS event for files_write_read")

output = step_success_events[-1]["payload"]["output"]
data = output["value"]["data"]
if output["text"] != "done":
    raise SystemExit(f"Expected final text done, got: {output['text']}")
if data["tool_call_count"] != 2:
    raise SystemExit(f"Unexpected persisted tool_call_count: {data['tool_call_count']}")
if data["stop_reason"] != "final":
    raise SystemExit(f"Unexpected stop reason: {data['stop_reason']}")

print(json.dumps({"run_id": run_id, "status": status}, indent=2))
PY
