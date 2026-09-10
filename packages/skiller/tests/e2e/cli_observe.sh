#!/usr/bin/env bash
set -euo pipefail

input_text="${1:-observed-value}"
tmpdir="$(mktemp -d)"
observer_pid=""

cleanup() {
  if [[ -n "${observer_pid}" ]] && kill -0 "${observer_pid}" 2>/dev/null; then
    kill "${observer_pid}" 2>/dev/null || true
    wait "${observer_pid}" 2>/dev/null || true
  fi
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

cd "$(dirname "$0")/../../../.."

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
observe_output="${tmpdir}/observe.jsonl"
observe_error="${tmpdir}/observe.stderr"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e/skills/observe_cli_e2e.yaml
)"
run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"

PYTHONPATH=packages/skiller/src timeout 20s "${runtime_python}" -m skiller observe \
  "${run_id}" --tail 100 >"${observe_output}" 2>"${observe_error}" &
observer_pid="$!"

if ! python3 - "${observe_output}" "${observer_pid}" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

output_path = Path(sys.argv[1])
observer_pid = int(sys.argv[2])
deadline = time.monotonic() + 10
offset = 0
pending = b""

while time.monotonic() < deadline:
    data = output_path.read_bytes()
    if len(data) < offset:
        offset = 0
        pending = b""
    pending += data[offset:]
    offset = len(data)

    lines = pending.split(b"\n")
    pending = lines.pop()
    for line in lines:
        if not line:
            continue
        frame = json.loads(line)
        if frame.get("kind") == "wait":
            raise SystemExit(0)

    try:
        os.kill(observer_pid, 0)
    except OSError as exc:
        raise SystemExit("Observer exited before wait frame") from exc
    time.sleep(0.1)

raise SystemExit("Observer did not emit wait frame")
PY
then
  cat "${observe_error}" >&2
  exit 1
fi

PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller input receive \
  "${run_id}" --text "${input_text}" >/dev/null

if wait "${observer_pid}"; then
  observer_pid=""
else
  observer_status="$?"
  printf 'Observer failed with status %s\n' "${observer_status}" >&2
  cat "${observe_error}" >&2
  exit 1
fi

OBSERVE_OUTPUT="${observe_output}" RUN_ID="${run_id}" python3 - <<'PY'
import json
import os
from pathlib import Path

frames = [
    json.loads(line)
    for line in Path(os.environ["OBSERVE_OUTPUT"]).read_text(encoding="utf-8").splitlines()
]
kinds = [frame["kind"] for frame in frames]

assert kinds[0] == "start", frames
assert kinds.count("wait") == 1, frames
assert kinds[-1] == "stop", frames

wait_index = kinds.index("wait")
assert frames[wait_index]["wait_type"] == "input", frames
assert any(
    frame["kind"] == "event" and frame["event"]["type"] == "INPUT_RECEIVED"
    for frame in frames[wait_index + 1 :]
), frames
assert frames[-1]["status"] == "succeeded", frames

print(json.dumps({"run_id": os.environ["RUN_ID"], "status": "SUCCEEDED"}, indent=2))
PY
