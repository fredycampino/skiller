#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"

cd "$(dirname "$0")/../../../../.."

export HOME="${tmpdir}/home"
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

mkdir -p "${HOME}/.skiller/settings"
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
    },
    "bedrock": {
      "profile": "test-bedrock-profile",
      "model": "us.anthropic.claude-sonnet-4-6",
      "timeout_seconds": 120,
      "window_width_tokens": 200000
    }
  }
}
JSON

run_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller run \
    --file packages/skiller/tests/e2e/skills/notify_cli_e2e.yaml \
    --detach
)"

run_id="$(RUN_OUTPUT="${run_output}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["RUN_OUTPUT"])
print(payload["run_id"])
PY
)"

models_output="$(
  PYTHONPATH=packages/skiller/src "${runtime_python}" -m skiller agent models "${run_id}"
)"

MODELS_OUTPUT="${models_output}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["MODELS_OUTPUT"])

assert payload["status"] == "OK", payload
assert payload["ok"] is True, payload
assert set(payload) == {"run_id", "status", "ok", "providers"}, payload

providers = payload["providers"]
provider_names = [provider["name"] for provider in providers]
assert provider_names == ["minimax", "codex", "bedrock"], provider_names
assert "null" not in provider_names
assert "fake" not in provider_names

for provider in providers:
    assert set(provider) == {"name", "source", "models"}, provider
    assert provider["source"] == "global", provider
    for model in provider["models"]:
        assert set(model) == {"name", "active"}, model

codex = next(provider for provider in providers if provider["name"] == "codex")
minimax = next(provider for provider in providers if provider["name"] == "minimax")
bedrock = next(provider for provider in providers if provider["name"] == "bedrock")

codex_models = {model["name"]: model for model in codex["models"]}
minimax_models = {model["name"]: model for model in minimax["models"]}
bedrock_models = {model["name"]: model for model in bedrock["models"]}

assert codex_models["gpt-5.5"]["active"] is True, codex
assert codex_models["gpt-5.4"]["active"] is False, codex
assert minimax_models["MiniMax-M2.7"]["active"] is False, minimax
assert bedrock_models["us.anthropic.claude-sonnet-4-6"]["active"] is False, bedrock

serialized = json.dumps(payload)
for forbidden in (
    "api_key",
    "credentials_file",
    "profile",
    "timeout_seconds",
    "window_width_tokens",
    "test-minimax-key",
    "test-bedrock-profile",
):
    assert forbidden not in serialized, forbidden

print(
    json.dumps(
        {
            "run_id": "agent-models",
            "status": "SUCCEEDED",
        },
        indent=2,
    )
)
PY
