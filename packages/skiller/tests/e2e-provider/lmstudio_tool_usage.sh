#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
base_url="${LMSTUDIO_BASE_URL:-http://localhost:1234/v1}"
api_key="${LMSTUDIO_API_KEY:-lm-studio}"
model="${LMSTUDIO_MODEL:-google/gemma-4-12b-qat}"
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

LMSTUDIO_BASE_URL="${base_url}" \
LMSTUDIO_API_KEY="${api_key}" \
LMSTUDIO_MODEL="${model}" \
LMSTUDIO_TIMEOUT_SECONDS="${timeout_seconds}" \
PYTHONPATH=packages/skiller/src \
"${runtime_python}" - <<'PY'
import json
import os

from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.agent.llm.model import (
    LLMSystemMessage,
    LLMToolChoiceMode,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_lmstudio import (
    AgentLMStudioLLMModel,
    AgentLMStudioProvider,
    LMStudioLLMRequest,
)
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
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


model = AgentLMStudioLLMModel(os.environ["LMSTUDIO_MODEL"])
provider = AgentLMStudioProvider(
    model=model,
    api_key=os.environ["LMSTUDIO_API_KEY"],
    base_url=os.environ["LMSTUDIO_BASE_URL"],
    timeout_seconds=float(os.environ["LMSTUDIO_TIMEOUT_SECONDS"]),
    window_width_tokens=model.model_context_window_tokens,
)
client = LLMClientFactory().resolve(provider)

command = "echo skiller-lmstudio-tool-usage-ok"
response = client.generate(
    LMStudioLLMRequest(
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
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        },
        indent=2,
        sort_keys=True,
    )
)
PY
