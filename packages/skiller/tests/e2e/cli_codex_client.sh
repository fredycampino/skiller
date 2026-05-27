#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

runtime_python="${SKILLER_RUNTIME_PYTHON:-./.venv/bin/python}"
credentials_file="${SKILLER_OPENAI_CODEX_CREDENTIALS_FILE:-${HOME}/.skiller/secrets/openai-codex.json}"

if [[ ! -x "${runtime_python}" ]]; then
  printf 'Missing runtime python: %s\n' "${runtime_python}" >&2
  exit 1
fi

if [[ "${RUN_CODEX_CLIENT_E2E:-0}" != "1" ]]; then
  python3 - <<'PY'
import json

print(json.dumps({
    "run_id": None,
    "status": "SKIPPED",
    "reason": "set RUN_CODEX_CLIENT_E2E=1 to run Codex client e2e",
}, indent=2))
PY
  exit 0
fi

if [[ ! -f "${credentials_file}" ]]; then
  CREDENTIALS_FILE="${credentials_file}" python3 - <<'PY'
import json
import os

print(json.dumps({
    "run_id": None,
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
from skiller.domain.agent.agent_config_model import (
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm_model import (
    LLMRequest,
    LLMSystemMessage,
    LLMToolChoice,
    LLMUserMessage,
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


model = os.environ.get("SKILLER_OPENAI_CODEX_MODEL", "gpt-5.5")
provider = AgentLLMProviderConfig(
    provider_type=AgentLLMProviderType.CODEX,
    model=model,
    api_key=None,
    timeout_seconds=120,
    context_window_tokens=100000,
    credentials_file=os.environ["SKILLER_OPENAI_CODEX_CREDENTIALS_FILE"],
)
client = LLMClientFactory().create(provider)

text_marker = "skiller-codex-client-text-ok"
text_response = client.generate(
    LLMRequest(
        model=model,
        messages=(
            LLMSystemMessage("Reply with the requested exact text only."),
            LLMUserMessage(f"Reply exactly: {text_marker}"),
        ),
    )
)
if not text_response.ok:
    raise SystemExit(text_response.error or "Codex text request failed")
if text_response.content != text_marker:
    raise SystemExit(f"Unexpected Codex text response: {text_response.content!r}")

command = "echo skiller-codex-tool-ok"
tool_response = client.generate(
    LLMRequest(
        model=model,
        messages=(
            LLMSystemMessage("You must call the requested tool. Do not answer in text."),
            LLMUserMessage(f"Call the shell tool with command: {command}"),
        ),
        tools=(ShellSmokeTool(),),
        tool_choice=LLMToolChoice.tool("shell"),
    )
)
if not tool_response.ok:
    raise SystemExit(tool_response.error or "Codex tool request failed")
if len(tool_response.tool_calls) != 1:
    raise SystemExit("Codex response did not include exactly one tool call")

tool_call = tool_response.tool_calls[0]
if tool_call.function.name != "shell":
    raise SystemExit(f"Unexpected tool call: {tool_call.function.name}")
if json.loads(tool_call.function.arguments_json) != {"command": command}:
    raise SystemExit(f"Unexpected tool arguments: {tool_call.function.arguments_json}")

print(json.dumps({
    "run_id": None,
    "status": "SUCCEEDED",
}, indent=2))
PY
