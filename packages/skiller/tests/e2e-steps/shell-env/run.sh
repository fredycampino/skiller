#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../../.."

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

output_path="${tmpdir}/event.json"
export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e-steps/shell-env/shell-env.yaml \
    --arg "output_dir=${tmpdir}"
)"

run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
status="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"

if [[ "${status}" != "SUCCEEDED" ]]; then
  printf 'Unexpected run status: %s\n' "${status}" >&2
  exit 1
fi

python3 - "${output_path}" "${run_id}" <<'PY'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
if not output_path.is_file():
    raise SystemExit(f"Expected output file was not created: {output_path}")

actual = json.loads(output_path.read_text(encoding="utf-8"))
expected = {
    "update_id": 42,
    "message": {
        "chat": {"id": 1001},
        "text": "hello",
    },
}
if actual != expected:
    raise SystemExit(f"Unexpected environment JSON. expected={expected!r} actual={actual!r}")

print(json.dumps({"run_id": sys.argv[2], "status": "SUCCEEDED"}, indent=2))
PY
