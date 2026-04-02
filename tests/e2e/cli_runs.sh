#!/usr/bin/env bash
set -euo pipefail

webhook_key="${1:-$(date +%s%N)}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=src "${runtime_python}" -m skiller run \
  --file tests/e2e/skills/wait_input_cli_e2e.yaml \
  >/dev/null 2>&1

PYTHONPATH=src "${runtime_python}" -m skiller run \
  --file tests/e2e/skills/wait_webhook_cli_e2e.yaml \
  --arg "key=${webhook_key}" \
  >/dev/null 2>&1

runs_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller runs
)"

waiting_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller runs --status WAITING
)"

RUNS_OUTPUT="${runs_output}" WAITING_OUTPUT="${waiting_output}" python3 - <<'PY'
import json
import os

runs = json.loads(os.environ["RUNS_OUTPUT"])
waiting = json.loads(os.environ["WAITING_OUTPUT"])

assert isinstance(runs, list)
assert isinstance(waiting, list)
assert len(waiting) >= 2

input_run = next((item for item in waiting if item.get("wait_type") == "input"), None)
webhook_run = next((item for item in waiting if item.get("wait_type") == "webhook"), None)

assert input_run is not None, waiting
assert webhook_run is not None, waiting
assert "wait_detail" not in input_run or input_run["wait_detail"] in ("", None)
assert str(webhook_run.get("wait_detail", "")).startswith("test:"), webhook_run

print(
    json.dumps(
        {
            "run_id": "runs",
            "status": "SUCCEEDED",
        },
        indent=2,
    )
)
PY
