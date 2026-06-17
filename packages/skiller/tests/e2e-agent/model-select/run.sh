#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"

cd "$(dirname "$0")/../../../../.."

export HOME="${tmpdir}/home"
export AGENT_DB_PATH="${tmpdir}/runtime.db"
export AGENT_WEBHOOKS_HOST="127.0.0.1"
export AGENT_WEBHOOKS_PORT="${SKILLER_TEST_WEBHOOK_PORT:-18084}"
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

mkdir -p "${HOME}/.skiller/settings" "${tmpdir}/flow"
cat >"${HOME}/.skiller/settings/agent.json" <<'JSON'
{
  "llm": {
    "default_provider": "codex"
  },
  "providers": {
    "codex": {
      "credentials_file": "~/.skiller/secrets/codex.json",
      "model": "gpt-5.5",
      "timeout_seconds": 120,
      "window_width_tokens": 1050000
    },
    "minimax": {
      "api_key": "test-minimax-key",
      "model": "MiniMax-M2.7",
      "timeout_seconds": 30,
      "window_width_tokens": 204800
    }
  }
}
JSON

cat >"${tmpdir}/flow/agent.json" <<'JSON'
{
  "llm": {
    "default_provider": "codex"
  }
}
JSON

cat >"${tmpdir}/flow/agent.yaml" <<'YAML'
name: model_select_minimax_e2e
description: "CLI e2e for selecting MiniMax model"
version: "0.1"
start: show_message

inputs: {}

steps:
  - notify: show_message
    message: "model select smoke ok"
YAML

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file "${tmpdir}/flow/agent.yaml" \
    --detach
)"

run_id="$(RUN_OUTPUT="${run_output}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["RUN_OUTPUT"])
print(payload["run_id"])
PY
)"

before_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller agent models "${run_id}"
)"

BEFORE_OUTPUT="${before_output}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["BEFORE_OUTPUT"])
providers = {provider["name"]: provider for provider in payload["providers"]}
codex_models = {model["name"]: model for model in providers["codex"]["models"]}
minimax_models = {model["name"]: model for model in providers["minimax"]["models"]}

assert payload["status"] == "OK", payload
assert providers["codex"]["source"] == "global", providers["codex"]
assert providers["minimax"]["source"] == "global", providers["minimax"]
assert codex_models["gpt-5.5"]["active"] is True, providers["codex"]
assert minimax_models["MiniMax-M2.7"]["active"] is False, providers["minimax"]
assert minimax_models["MiniMax-M2.5"]["active"] is False, providers["minimax"]
PY

select_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller agent model "${run_id}" \
    --provider minimax \
    --model MiniMax-M2.5
)"

RUN_ID="${run_id}" SELECT_OUTPUT="${select_output}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["SELECT_OUTPUT"])
run_id = os.environ["RUN_ID"]

assert payload == {
    "run_id": run_id,
    "provider": "minimax",
    "model": "MiniMax-M2.5",
    "status": "OK",
    "ok": True,
}, payload
PY

after_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller agent models "${run_id}"
)"

GLOBAL_CONFIG="${HOME}/.skiller/settings/agent.json" \
LOCAL_CONFIG="${tmpdir}/flow/agent.json" \
AFTER_OUTPUT="${after_output}" \
python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["AFTER_OUTPUT"])
global_payload = json.loads(Path(os.environ["GLOBAL_CONFIG"]).read_text(encoding="utf-8"))
local_payload = json.loads(Path(os.environ["LOCAL_CONFIG"]).read_text(encoding="utf-8"))

assert payload["status"] == "OK", payload
assert payload["ok"] is True, payload

providers = {provider["name"]: provider for provider in payload["providers"]}
codex_models = {model["name"]: model for model in providers["codex"]["models"]}
minimax_models = {model["name"]: model for model in providers["minimax"]["models"]}

assert codex_models["gpt-5.5"]["active"] is False, providers["codex"]
assert minimax_models["MiniMax-M2.5"]["active"] is True, providers["minimax"]
assert minimax_models["MiniMax-M2.7"]["active"] is False, providers["minimax"]

assert local_payload == {"llm": {"default_provider": "minimax"}}, local_payload
assert global_payload["llm"]["default_provider"] == "codex", global_payload
assert global_payload["providers"]["minimax"]["model"] == "MiniMax-M2.5", global_payload
assert "providers" not in local_payload, local_payload

serialized = json.dumps(payload)
for forbidden in (
    "api_key",
    "credentials_file",
    "timeout_seconds",
    "window_width_tokens",
    "test-minimax-key",
):
    assert forbidden not in serialized, forbidden

print(
    json.dumps(
        {
            "run_id": "agent-model-select-minimax",
            "status": "SUCCEEDED",
        },
        indent=2,
    )
)
PY
