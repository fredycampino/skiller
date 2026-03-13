#!/usr/bin/env bash
set -euo pipefail

explicit_run_id="${1:-550e8400-e29b-41d4-a716-446655440000}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

run_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller run \
    --file tests/e2e/skills/notify_cli_e2e.yaml \
    --run-id "${explicit_run_id}"
)"

RUN_OUTPUT="${run_output}" EXPLICIT_RUN_ID="${explicit_run_id}" python3 -c '
import json
import os

payload = json.loads(os.environ["RUN_OUTPUT"])
expected_run_id = os.environ["EXPLICIT_RUN_ID"]

if payload["run_id"] != expected_run_id:
    raise SystemExit(f"unexpected run_id in run output: {payload['run_id']} != {expected_run_id}")

if payload["status"] != "SUCCEEDED":
    raise SystemExit(f"unexpected run status: {payload['status']}")
'

status_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller status "${explicit_run_id}"
)"

STATUS_OUTPUT="${status_output}" EXPLICIT_RUN_ID="${explicit_run_id}" python3 -c '
import json
import os
import sys

payload = json.loads(os.environ["STATUS_OUTPUT"])
expected_run_id = os.environ["EXPLICIT_RUN_ID"]

if payload["id"] != expected_run_id:
    raise SystemExit(f"unexpected run_id in status output: {payload['id']} != {expected_run_id}")

if payload["status"] != "SUCCEEDED":
    raise SystemExit(f"unexpected persisted status: {payload['status']}")

print(json.dumps({"run_id": expected_run_id, "status": payload["status"]}, indent=2))
'
