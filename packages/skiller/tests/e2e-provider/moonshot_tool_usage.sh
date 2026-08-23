#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
api_key_file="${AGENT_MOONSHOT_API_KEY_FILE:-${HOME}/.skiller/secrets/moonshot_api_key}"

if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_MOONSHOT_PROVIDER_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "set RUN_PROVIDER_E2E=1 or RUN_MOONSHOT_PROVIDER_E2E=1 to run Moonshot provider e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

if [[ -z "${AGENT_MOONSHOT_API_KEY:-}" && ! -f "${api_key_file}" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "AGENT_MOONSHOT_API_KEY is not configured and Moonshot api key file does not exist",
}, indent=2))
PY
  exit 0
fi

if [[ -z "${AGENT_MOONSHOT_API_KEY:-}" ]]; then
  AGENT_MOONSHOT_API_KEY="$(<"${api_key_file}")"
  export AGENT_MOONSHOT_API_KEY
fi

PYTHONPATH=packages/skiller/src \
"${runtime_python}" - <<'PY'
import json
import os

from skiller.domain.agent.llm.finish_type import LLMFinishType
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
    model=os.environ.get("AGENT_MOONSHOT_MODEL", "kimi-k3"),
    context_window_tokens=256000,
    max_output_tokens=4096,
)
provider = OpenAILLMProviderDefinition(
    name="moonshot",
    timeout_seconds=float(os.environ.get("AGENT_MOONSHOT_TIMEOUT_SECONDS", "120")),
    models=(model,),
    enabled=True,
    base_url="https://api.moonshot.ai/v1",
    temperature=1,
    top_p=0.95,
    parallel_tool_calls=True,
    tool_choice=LLMToolChoiceMode.AUTO,
    api_key_source=LLMApiKeySource(
        type=LLMApiKeySourceType.ENV,
        value="AGENT_MOONSHOT_API_KEY",
    ),
    options={},
)
client = DefaultLLMClientResolver(
    api_key_datasource=OpenAIApiKeyDatasource(env=os.environ),
).resolve(provider)

command = "echo skiller-moonshot-tool-usage-ok"
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
        top_p=provider.top_p,
    )
)

if response.finish_type != LLMFinishType.TOOL_CALLS:
    raise SystemExit(response.error or "Moonshot tool request failed")
if len(response.tool_calls) != 1:
    raise SystemExit("Moonshot response did not include exactly one tool call")
if response.usage is None:
    raise SystemExit("Moonshot tool-call response did not include usage")
if response.usage.total_tokens is None or response.usage.total_tokens <= 0:
    raise SystemExit("Moonshot tool-call response usage.total_tokens was empty")

tool_call = response.tool_calls[0]
if tool_call.function.name != "shell":
    raise SystemExit(f"Unexpected tool call: {tool_call.function.name}")
if json.loads(tool_call.function.arguments_json) != {"command": command}:
    raise SystemExit(f"Unexpected tool arguments: {tool_call.function.arguments_json}")

print(
    json.dumps(
        {
            "status": "SUCCEEDED",
            "provider": "moonshot",
            "model": response.model.value,
            "finish_type": response.finish_type.value,
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
