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

run_skill() {
  local skill_file="$1"
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file "${skill_file}"
}

run_id_from_json() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])'
}

wait_for_status() {
  local run_id="$1"
  local expected="$2"

  for _ in $(seq 1 80); do
    local status
    status="$(
      PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller status "${run_id}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])'
    )"
    if [[ "${status}" == "${expected}" ]]; then
      return 0
    fi
    sleep 0.1
  done

  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller status "${run_id}" >&2
  printf 'Run %s did not reach status %s\n' "${run_id}" "${expected}" >&2
  return 1
}

receive_input() {
  local run_id="$1"
  local text="$2"
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller input receive \
    "${run_id}" \
    --text "${text}" \
    >/dev/null
}

assert_cleaned_run() {
  local run_id="$1"
  local expected_status="$2"
  python3 - "${AGENT_DB_PATH}" "${run_id}" "${expected_status}" <<'PY'
import json
import sqlite3
import sys

db_path = sys.argv[1]
run_id = sys.argv[2]
expected_status = sys.argv[3]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

events = conn.execute(
    """
    SELECT event_type, body_json
    FROM log_events
    WHERE run_id = ?
    ORDER BY sequence ASC
    """,
    (run_id,),
).fetchall()
event_types = [row["event_type"] for row in events]
assert event_types == ["RUN_CREATE", "RUN_FINISHED"], event_types

finished_payload = json.loads(events[-1]["body_json"])
assert finished_payload["status"] == expected_status, finished_payload

run = conn.execute(
    """
    SELECT status, inputs_json, step_executions_json, steering_queue_json, cancel_reason
    FROM runs
    WHERE id = ?
    """,
    (run_id,),
).fetchone()
assert run is not None, run_id
assert run["status"] == expected_status, dict(run)
assert json.loads(run["inputs_json"]) == {}, run["inputs_json"]
assert json.loads(run["step_executions_json"]) == {}, run["step_executions_json"]
assert json.loads(run["steering_queue_json"]) == [], run["steering_queue_json"]
assert run["cancel_reason"] is None, run["cancel_reason"]

waits = conn.execute(
    "SELECT COUNT(*) AS total FROM waits WHERE run_id = ?",
    (run_id,),
).fetchone()
assert waits["total"] == 0, waits["total"]

external_events = conn.execute(
    """
    SELECT COUNT(*) AS total
    FROM external_events
    WHERE run_id = ? OR consumed_by_run_id = ?
    """,
    (run_id, run_id),
).fetchone()
assert external_events["total"] == 0, external_events["total"]

agent_context_table = conn.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table' AND name = 'agent_context_entries'
    """
).fetchone()
if agent_context_table is not None:
    agent_context_entries = conn.execute(
        "SELECT COUNT(*) AS total FROM agent_context_entries WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert agent_context_entries["total"] == 0, agent_context_entries["total"]
PY
}

success_output="$(
  run_skill packages/skiller/tests/e2e/skills/cleanup_success_cli_e2e.yaml
)"
success_run_id="$(printf '%s\n' "${success_output}" | run_id_from_json)"
wait_for_status "${success_run_id}" "WAITING"
receive_input "${success_run_id}" "cleanup-sensitive-success"
wait_for_status "${success_run_id}" "WAITING"
receive_input "${success_run_id}" "exit"
wait_for_status "${success_run_id}" "SUCCEEDED"
assert_cleaned_run "${success_run_id}" "SUCCEEDED"

error_output="$(
  run_skill packages/skiller/tests/e2e/skills/cleanup_error_cli_e2e.yaml
)"
error_run_id="$(printf '%s\n' "${error_output}" | run_id_from_json)"
wait_for_status "${error_run_id}" "WAITING"
receive_input "${error_run_id}" "cleanup-sensitive-error"
wait_for_status "${error_run_id}" "FAILED"
assert_cleaned_run "${error_run_id}" "FAILED"

python3 - "${success_run_id}" "${error_run_id}" <<'PY'
import json
import sys

print(
    json.dumps(
        {
            "run_id": ",".join(sys.argv[1:]),
            "status": "SUCCEEDED",
        },
        indent=2,
    )
)
PY
