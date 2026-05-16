#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -t 1 ]]; then
  green=$'\033[32m'
  yellow=$'\033[33m'
  red=$'\033[31m'
  reset=$'\033[0m'
else
  green=""
  yellow=""
  red=""
  reset=""
fi

failures=0

run_case() {
  local label="$1"
  shift

  echo "==> ${label}"

  local output_file
  output_file="$(mktemp)"

  if ! "$@" 2>&1 | tee "${output_file}"; then
    printf '%s[FAIL]%s command exited with non-zero status\n' "${red}" "${reset}"
    rm -f "${output_file}"
    failures=$((failures + 1))
    return
  fi

  local output
  output="$(cat "${output_file}")"
  rm -f "${output_file}"

  local result
  result="$(
    CLI_OUTPUT="${output}" GREEN="${green}" YELLOW="${yellow}" RED="${red}" RESET="${reset}" python3 -c '
import json
import os

raw = os.environ["CLI_OUTPUT"]
start = raw.rfind("{")
payload = None

while start != -1:
    candidate = raw[start:].strip()
    try:
        payload = json.loads(candidate)
        break
    except json.JSONDecodeError:
        start = raw.rfind("{", 0, start)

if payload is None:
    raise SystemExit(raw)

status = str(payload.get("status", "")).upper()
run_id = payload.get("run_id")
reason = payload.get("reason")
green = os.getenv("GREEN", "")
yellow = os.getenv("YELLOW", "")
red = os.getenv("RED", "")
reset = os.getenv("RESET", "")

if status == "SUCCEEDED":
    print(f"PASS:{green}[PASS]{reset} {run_id}")
elif status == "SKIPPED":
    display_reason = reason or "no reason"
    print(f"SKIP:{yellow}[SKIP]{reset} {display_reason}")
else:
    print(f"FAIL:{red}[FAIL]{reset} status={status or "UNKNOWN"} run_id={run_id or "-"}")
    print(payload)
'
  )"

  printf '%s\n' "${result#*:}"

  if [[ "${result}" == FAIL:* ]]; then
    failures=$((failures + 1))
  fi
}

run_case "minimal" ./minimal/run.sh "2026-05-16"
echo
run_case "tools-calls" ./tools-calls/run.sh

if [[ "${failures}" -gt 0 ]]; then
  exit 1
fi
