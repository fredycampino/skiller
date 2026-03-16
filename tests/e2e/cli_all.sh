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

run_cli() {
  local label="$1"
  shift

  echo "==> ${label}"

  local output
  if output="$("$@" 2>&1)"; then
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
    print(f"{green}[PASS]{reset} {run_id}")
elif status == "SKIPPED":
    print(f"{yellow}[SKIP]{reset} {reason or "no reason"}")
else:
    print(f"{red}[FAIL]{reset} status={status or "UNKNOWN"} run_id={run_id or "-"}")
    print(payload)
'
    return
  fi

  printf '%s\n' "${output}"
  printf '%s[FAIL]%s command exited with non-zero status\n' "${red}" "${reset}"
}

run_cli "cli_notify.sh" ./cli_notify.sh
echo
echo
run_cli "cli_assign.sh" ./cli_assign.sh "dependency timeout"
echo
run_cli "cli_switch.sh" ./cli_switch.sh "retry"
echo
run_cli "cli_when.sh" ./cli_when.sh
echo
run_cli "cli_wait_webhook.sh" ./cli_wait_webhook.sh
echo
run_cli "cli_llm_prompt.sh" ./cli_llm_prompt.sh
echo
run_cli "cli_mcp_stdio.sh" ./cli_mcp_stdio.sh "hola-e2e"
