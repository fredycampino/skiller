#!/usr/bin/env bash
set -euo pipefail

content_text="${1:-hello-shell-e2e}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

cd "$(dirname "$0")/../.."

script_path="${tmpdir}/script.sh"
output_file="${tmpdir}/shell-e2e.txt"

cat > "${script_path}" <<'SH'
#!/usr/bin/env sh
set -eu
output_path="$1"
content="$2"
printf '%s' "${content}" > "${output_path}"
printf 'shell-script-ok\n'
SH
chmod +x "${script_path}"

export AGENT_DB_PATH="${tmpdir}/runtime.db"
runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

run_output="$(
  PYTHONPATH=src "${runtime_python}" -m skiller run \
    --file tests/e2e/skills/shell_cli_e2e.yaml \
    --arg "script_path=${script_path}" \
    --arg "output_path=${output_file}" \
    --arg "content=${content_text}"
)"

run_id="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
status="$(printf '%s\n' "${run_output}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"

if [[ "${status}" != "SUCCEEDED" ]]; then
  printf 'Unexpected run status: %s\n' "${status}" >&2
  exit 1
fi

if [[ ! -f "${output_file}" ]]; then
  printf 'Expected output file was not created: %s\n' "${output_file}" >&2
  exit 1
fi

actual_content="$(cat "${output_file}")"
if [[ "${actual_content}" != "${content_text}" ]]; then
  printf 'Unexpected output file content. expected=%s actual=%s\n' "${content_text}" "${actual_content}" >&2
  exit 1
fi

python3 - "${run_id}" <<'PY'
import json
import sys

print(json.dumps({"run_id": sys.argv[1], "status": "SUCCEEDED"}, indent=2))
PY
