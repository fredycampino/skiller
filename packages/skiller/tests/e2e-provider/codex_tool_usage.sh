#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
credentials_file="${SKILLER_OPENAI_CODEX_CREDENTIALS_FILE:-${HOME}/.skiller/secrets/openai-codex.json}"

if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_CODEX_PROVIDER_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "set RUN_PROVIDER_E2E=1 or RUN_CODEX_PROVIDER_E2E=1 to run Codex provider e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

if [[ ! -f "${credentials_file}" ]]; then
  CREDENTIALS_FILE="${credentials_file}" python3 - <<'PY'
import json
import os

print(json.dumps({
    "status": "SKIPPED",
    "reason": f"Codex credentials file does not exist: {os.environ['CREDENTIALS_FILE']}",
}, indent=2))
PY
  exit 0
fi

PYTHONPATH=packages/skiller/src \
SKILLER_OPENAI_CODEX_CREDENTIALS_FILE="${credentials_file}" \
"${runtime_python}" - <<'PY'
import json
import os

from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexLLMModel,
    AgentCodexProvider,
)
from skiller.domain.agent.llm_model import LLMSystemMessage, LLMUserMessage
from skiller.domain.agent.llm_request import CodexLLMRequest
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


model = AgentCodexLLMModel(os.environ.get("SKILLER_OPENAI_CODEX_MODEL", "gpt-5.5"))
provider = AgentCodexProvider(
    model=model,
    timeout_seconds=120,
    window_width_tokens=100000,
    credentials_file=os.environ["SKILLER_OPENAI_CODEX_CREDENTIALS_FILE"],
)
client = LLMClientFactory().resolve(provider)

command = "echo skiller-codex-tool-usage-ok"
response = client.generate(
    CodexLLMRequest(
        model=model,
        messages=(
            LLMSystemMessage("You must call the requested tool. Do not answer in text."),
            LLMUserMessage(f"Call the shell tool with command: {command}"),
        ),
        tools=(ShellSmokeTool(),),
        parallel_tool_calls=True,
    )
)

if not response.ok:
    raise SystemExit(response.error or "Codex tool request failed")
if len(response.tool_calls) != 1:
    raise SystemExit("Codex response did not include exactly one tool call")
if response.usage is None:
    raise SystemExit("Codex tool-call response did not include usage")
if response.usage.total_tokens is None or response.usage.total_tokens <= 0:
    raise SystemExit("Codex tool-call response usage.total_tokens was empty")

tool_call = response.tool_calls[0]
if tool_call.function.name != "shell":
    raise SystemExit(f"Unexpected tool call: {tool_call.function.name}")
if json.loads(tool_call.function.arguments_json) != {"command": command}:
    raise SystemExit(f"Unexpected tool arguments: {tool_call.function.arguments_json}")

print(
    json.dumps(
        {
            "status": "SUCCEEDED",
            "provider": "codex",
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
