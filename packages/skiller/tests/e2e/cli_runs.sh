#!/usr/bin/env bash
set -euo pipefail

webhook_key="${1:-$(date +%s%N)}"
tmpdir="$(mktemp -d)"

cd "$(dirname "$0")/../../../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_WEBHOOKS_HOST="127.0.0.1"
export AGENT_WEBHOOKS_PORT="${SKILLER_TEST_WEBHOOK_PORT:-18083}"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

cleanup() {
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller server stop >/dev/null 2>&1 || true
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
  --file packages/skiller/tests/e2e/skills/wait_input_cli_e2e.yaml \
  >/dev/null 2>&1

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller server start >/dev/null

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
  --file packages/skiller/tests/e2e/skills/wait_webhook_cli_e2e.yaml \
  --arg "key=${webhook_key}" \
  >/dev/null 2>&1

runs_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller runs
)"

waiting_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller runs --status WAITING
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
