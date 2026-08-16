#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
base_url="${LMSTUDIO_BASE_URL:-http://localhost:1234/v1}"
api_key="${LMSTUDIO_API_KEY:-lm-studio}"
TEST_LMSTUDIO_MODEL="${TEST_LMSTUDIO_MODEL:-google/gemma-4-12b-qat}"
timeout_seconds="${LMSTUDIO_TIMEOUT_SECONDS:-120}"

if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_LMSTUDIO_PROVIDER_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "set RUN_PROVIDER_E2E=1 or RUN_LMSTUDIO_PROVIDER_E2E=1 to run LM Studio provider e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

# ─── LM Studio setup / health check ──────────────────────────────────────────

lmstudio_api_key_file="/home/fede/.skiller/secrets/lmstudio_api_key"
if [[ -f "${lmstudio_api_key_file}" ]]; then
  lmstudio_api_key="$(cat "${lmstudio_api_key_file}")"
else
  lmstudio_api_key="${api_key}"
fi

_lms_available() {
  command -v lms &>/dev/null
}

_model_loaded() {
  local expected="$1"
  local models
  models=$(curl -s \
    -H "Authorization: Bearer ${lmstudio_api_key}" \
    "${base_url}/models" 2>/dev/null | \
    python3 -c "import sys,json; data=json.load(sys.stdin); print('\n'.join(m.get('id','') for m in data.get('data',[])))" \
    2>/dev/null || true)
  echo "${models}" | grep -qE "^${expected}(:|$)"
}

if ! _lms_available; then
  printf 'FAIL: lms CLI not found in PATH\n' >&2
  exit 1
fi

if ! lms daemon ping &>/dev/null; then
  echo "Starting LM Studio daemon..."
  lms daemon up
  sleep 2
fi

if ! lms server status &>/dev/null; then
  echo "Starting LM Studio server on port 1234..."
  lms server start --port 1234
  sleep 2
fi

if ! _model_loaded "${TEST_LMSTUDIO_MODEL}"; then
  echo "Loading model ${TEST_LMSTUDIO_MODEL}..."
  lms load "${TEST_LMSTUDIO_MODEL}" --context-length 8000
  sleep 5
fi

echo "Verifying model is available..."
if ! _model_loaded "${TEST_LMSTUDIO_MODEL}"; then
  printf 'FAIL: model %s not loaded\n' "${TEST_LMSTUDIO_MODEL}" >&2
  lms ps 2>/dev/null || true
  exit 1
fi

echo "LM Studio ready with model: ${TEST_LMSTUDIO_MODEL}"
lms ps

_cleanup() {
  echo "Stopping LM Studio server..."
  lms server stop 2>/dev/null || true
}

trap _cleanup EXIT

LMSTUDIO_BASE_URL="${base_url}" \
LMSTUDIO_API_KEY="${api_key}" \
LMSTUDIO_MODEL="${TEST_LMSTUDIO_MODEL}" \
LMSTUDIO_TIMEOUT_SECONDS="${timeout_seconds}" \
PYTHONPATH=packages/skiller/src \
"${runtime_python}" - <<'PY'
import json
import os

from skiller.domain.agent.llm.model import (
    LLMSystemMessage,
    LLMToolChoiceMode,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import (
    LLMApiKeySource,
    LLMApiKeySourceType,
    LLMModelDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.default_llm_client_resolver import DefaultLLMClientResolver
from skiller.infrastructure.llm.openai.openai_api_key_datasource import (
    OpenAIApiKeyDatasource,
)


class ShellSmokeTool(ToolDefinition[ToolRequest]):
    name = "shell"
    description = "Run a shell command."

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run.",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        _ = input
        return ToolRequestResult.valid(ToolRequest())


model = LLMModelDefinition(
    model=os.environ["LMSTUDIO_MODEL"],
    context_window_tokens=8000,
)
provider = OpenAILLMProviderDefinition(
    name="lmstudio",
    models=(model,),
    enabled=True,
    base_url=os.environ["LMSTUDIO_BASE_URL"],
    timeout_seconds=float(os.environ["LMSTUDIO_TIMEOUT_SECONDS"]),
    temperature=0.2,
    top_p=1,
    max_output_tokens=4096,
    parallel_tool_calls=True,
    tool_choice=LLMToolChoiceMode.AUTO,
    api_key_source=LLMApiKeySource(
        type=LLMApiKeySourceType.VALUE,
        value=os.environ["LMSTUDIO_API_KEY"],
    ),
    options={},
)
client = DefaultLLMClientResolver(
    api_key_datasource=OpenAIApiKeyDatasource(env={}),
).resolve(provider)

command = "echo skiller-lmstudio-tool-usage-ok"
response = client.generate(
    OpenAILLMRequest(
        model=model,
        messages=(
            LLMSystemMessage("You must call the requested tool. Do not answer in text."),
            LLMUserMessage(f"Call the shell tool with command: {command}"),
        ),
        tools=(ShellSmokeTool(),),
        tool_choice=LLMToolChoiceMode.AUTO,
        parallel_tool_calls=True,
        temperature=provider.temperature,
        max_tokens=provider.max_output_tokens,
        top_p=provider.top_p,
    )
)

if not response.ok:
    raise SystemExit(response.error or "LM Studio tool request failed")
if len(response.tool_calls) != 1:
    raise SystemExit("LM Studio response did not include exactly one tool call")
if response.usage is None:
    raise SystemExit("LM Studio tool-call response did not include usage")
if response.usage.total_tokens is None or response.usage.total_tokens <= 0:
    raise SystemExit("LM Studio tool-call response usage.total_tokens was empty")

tool_call = response.tool_calls[0]
if tool_call.function.name != "shell":
    raise SystemExit(f"Unexpected tool call: {tool_call.function.name}")
if json.loads(tool_call.function.arguments_json) != {"command": command}:
    raise SystemExit(f"Unexpected tool arguments: {tool_call.function.arguments_json}")

print(
    json.dumps(
        {
            "status": "SUCCEEDED",
            "provider": "lmstudio",
            "base_url": os.environ["LMSTUDIO_BASE_URL"],
            "model": response.model.value,
            "finish_reason": response.finish_reason,
            "tool_calls": len(response.tool_calls),
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        },
        indent=2,
        sort_keys=True,
    )
)
PY
