#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
api_key_file="${AGENT_MINIMAX_API_KEY_FILE:-${HOME}/.skiller/secrets/minimax_api_key}"

if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_MINIMAX_PROVIDER_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "set RUN_PROVIDER_E2E=1 or RUN_MINIMAX_PROVIDER_E2E=1 to run MiniMax provider e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

if [[ -z "${AGENT_MINIMAX_API_KEY:-}" && ! -f "${api_key_file}" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "AGENT_MINIMAX_API_KEY is not configured and MiniMax api key file does not exist",
}, indent=2))
PY
  exit 0
fi

if [[ -z "${AGENT_MINIMAX_API_KEY:-}" ]]; then
  AGENT_MINIMAX_API_KEY="$(<"${api_key_file}")"
  export AGENT_MINIMAX_API_KEY
fi

PYTHONPATH=packages/skiller/src \
"${runtime_python}" - <<'PY'
import json
import os

from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_registry import (
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
)
from skiller.domain.agent.llm.model import LLMSystemMessage, LLMUserMessage
from skiller.domain.agent.llm.provider_minimax import MiniMaxLLMRequest
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


model = AgentMiniMaxLLMModel(os.environ.get("AGENT_MINIMAX_MODEL", "MiniMax-M2.7"))
provider = AgentMiniMaxProvider(
    model=model,
    api_key=os.environ["AGENT_MINIMAX_API_KEY"],
    timeout_seconds=float(os.environ.get("AGENT_MINIMAX_TIMEOUT_SECONDS", "120")),
    window_width_tokens=100000,
)
client = LLMClientFactory().resolve(provider)

command = "echo skiller-minimax-tool-usage-ok"
response = client.generate(
    MiniMaxLLMRequest(
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
    raise SystemExit(response.error or "MiniMax tool request failed")
if len(response.tool_calls) != 1:
    raise SystemExit("MiniMax response did not include exactly one tool call")
if response.usage is None:
    raise SystemExit("MiniMax tool-call response did not include usage")
if response.usage.total_tokens is None or response.usage.total_tokens <= 0:
    raise SystemExit("MiniMax tool-call response usage.total_tokens was empty")

tool_call = response.tool_calls[0]
if tool_call.function.name != "shell":
    raise SystemExit(f"Unexpected tool call: {tool_call.function.name}")
if json.loads(tool_call.function.arguments_json) != {"command": command}:
    raise SystemExit(f"Unexpected tool arguments: {tool_call.function.arguments_json}")

print(
    json.dumps(
        {
            "status": "SUCCEEDED",
            "provider": "minimax",
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
