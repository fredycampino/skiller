#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
profile="${AGENT_BEDROCK_PROFILE:-aternitybedrock}"
model="${AGENT_BEDROCK_MODEL:-us.anthropic.claude-opus-4-7}"
timeout_seconds="${AGENT_BEDROCK_TIMEOUT_SECONDS:-120}"
max_tokens="${AGENT_BEDROCK_MAX_TOKENS:-1024}"

if [[ "${RUN_PROVIDER_E2E:-0}" != "1" && "${RUN_BEDROCK_STREAMING_PROVIDER_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "status": "SKIPPED",
    "reason": "set RUN_PROVIDER_E2E=1 or RUN_BEDROCK_STREAMING_PROVIDER_E2E=1 to run Bedrock streaming provider e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

PYTHONPATH=packages/skiller/src \
AGENT_BEDROCK_PROFILE="${profile}" \
AGENT_BEDROCK_MODEL="${model}" \
AGENT_BEDROCK_TIMEOUT_SECONDS="${timeout_seconds}" \
AGENT_BEDROCK_MAX_TOKENS="${max_tokens}" \
"${runtime_python}" - <<'PY'
import json
import os

from skiller.domain.agent.llm.model import LLMSystemMessage, LLMUserMessage
from skiller.domain.agent.llm.provider_bedrock import (
    AgentBedrockLLMModel,
    BedrockLLMRequest,
)
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.bedrock.bedrock_request_logger import (
    BedrockFileLLMRequestLogger,
)
from skiller.infrastructure.llm.bedrock.bedrock_streaming_port import (
    BedrockStreamingLLMPort,
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


model = AgentBedrockLLMModel(os.environ["AGENT_BEDROCK_MODEL"])
client = BedrockStreamingLLMPort(
    profile=os.environ["AGENT_BEDROCK_PROFILE"],
    timeout_seconds=float(os.environ["AGENT_BEDROCK_TIMEOUT_SECONDS"]),
    request_logger=BedrockFileLLMRequestLogger(overwrite=True),
)

command = "echo skiller-bedrock-streaming-tool-usage-ok"
response = client.generate(
    BedrockLLMRequest(
        model=model,
        messages=(
            LLMSystemMessage("You must call the requested tool. Do not answer in text."),
            LLMUserMessage(f"Call the shell tool with command: {command}"),
        ),
        max_tokens=int(os.environ["AGENT_BEDROCK_MAX_TOKENS"]),
        tools=(ShellSmokeTool(),),
    )
)

if not response.ok:
    raise SystemExit(response.error or "Bedrock streaming tool request failed")
if len(response.tool_calls) != 1:
    raise SystemExit("Bedrock streaming response did not include exactly one tool call")
if response.usage is None:
    raise SystemExit("Bedrock streaming tool-call response did not include usage")
if response.usage.total_tokens is None or response.usage.total_tokens <= 0:
    raise SystemExit("Bedrock streaming tool-call response usage.total_tokens was empty")

tool_call = response.tool_calls[0]
if tool_call.function.name != "shell":
    raise SystemExit(f"Unexpected tool call: {tool_call.function.name}")
if json.loads(tool_call.function.arguments_json) != {"command": command}:
    raise SystemExit(f"Unexpected tool arguments: {tool_call.function.arguments_json}")

print(
    json.dumps(
        {
            "status": "SUCCEEDED",
            "provider": "bedrock-streaming",
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
