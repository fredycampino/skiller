from __future__ import annotations

import pytest

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilitiesResolver,
    CodexResponsesProtocol,
)
from skiller.infrastructure.llm.codex.codex_reasoning import (
    CODEX_DEFAULT_REASONING_EFFORT,
)
from skiller.infrastructure.llm.codex.codex_turn_session import (
    CODEX_TURN_STATE_HEADER,
    CodexTurnIdentity,
    CodexTurnSession,
)
from skiller.infrastructure.llm.codex.responses_general_mapper import ResponsesGeneralMapper
from skiller.infrastructure.llm.codex.responses_lite_mapper import (
    CODEX_RESPONSES_LITE_HEADER,
    ResponsesLiteMapper,
)

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


class _ShellTool(ToolDefinition[ToolRequest]):
    name = "shell"
    description = "run a command"

    def schema(self) -> ToolSchema:
        return ToolSchema(value={"type": "object"})

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        _ = input
        return ToolRequestResult.valid(ToolRequest())


def test_codex_model_capabilities_resolve_protocol_without_reasoning_policy() -> None:
    resolver = CodexModelCapabilitiesResolver()

    generic = resolver.resolve("gpt-5.5")
    sol = resolver.resolve("gpt-5.6-sol")
    future_lite = resolver.resolve("gpt-5.6-future")

    assert generic.protocol == CodexResponsesProtocol.GENERIC
    assert sol.protocol == CodexResponsesProtocol.LITE
    assert future_lite.protocol == CodexResponsesProtocol.LITE
    assert CODEX_DEFAULT_REASONING_EFFORT.value == "medium"


def test_generic_responses_mapper_adds_reasoning_without_lite_framing() -> None:
    request = CodexLLMRequest(
        messages=(
            LLMSystemMessage("system"),
            LLMUserMessage("hello"),
        ),
        model=_model("gpt-5.5", 1_050_000),
        parallel_tool_calls=True,
        session_id="session-1",
        tools=(_ShellTool(),),
    )
    kwargs = ResponsesGeneralMapper().to_kwargs(
        request,
        turn_session=_turn_session(model=request.model.value),
    )

    assert kwargs["instructions"] == "system"
    assert kwargs["tools"] == [
        {
            "type": "function",
            "name": "shell",
            "description": "run a command",
            "parameters": {"type": "object"},
        }
    ]
    assert kwargs["parallel_tool_calls"] is True
    assert kwargs["reasoning"] == {"effort": "medium"}
    assert kwargs["include"] == ["reasoning.encrypted_content"]
    assert CODEX_RESPONSES_LITE_HEADER not in kwargs["extra_headers"]


def test_lite_mapper_uses_lite_framing_and_replays_turn_state() -> None:
    tool_call = LLMToolCall(
        id="call-1",
        function=LLMToolCallFunction(
            name="shell",
            arguments_json='{"command":"pwd"}',
        ),
    )
    request = CodexLLMRequest(
        messages=(
            LLMSystemMessage("system"),
            LLMUserMessage("use shell"),
            LLMAssistantMessage(tool_calls=(tool_call,)),
            LLMToolMessage("result", tool_call_id="call-1"),
        ),
        model=_model("gpt-5.6-luna", 1_050_000),
        parallel_tool_calls=True,
        session_id="session-1",
        tools=(_ShellTool(),),
    )
    turn_session = _turn_session(model=request.model.value)
    turn_session.turn_state = "opaque-turn-state"
    turn_session.response_output_batches.append(
        (
            {
                "type": "reasoning",
                "id": "reasoning-1",
                "summary": [],
                "encrypted_content": "encrypted-reasoning",
            },
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "shell",
                "arguments": '{"command":"pwd"}',
            },
        )
    )

    kwargs = ResponsesLiteMapper().to_kwargs(
        request,
        turn_session=turn_session,
    )

    assert "instructions" not in kwargs
    assert "tools" not in kwargs
    assert kwargs["parallel_tool_calls"] is False
    assert kwargs["reasoning"] == {"effort": "medium", "context": "all_turns"}
    assert kwargs["include"] == ["reasoning.encrypted_content"]
    assert kwargs["extra_headers"][CODEX_RESPONSES_LITE_HEADER] == "true"
    assert kwargs["extra_headers"][CODEX_TURN_STATE_HEADER] == "opaque-turn-state"
    assert kwargs["input"][0] == {
        "type": "additional_tools",
        "role": "developer",
        "tools": [
            {
                "type": "namespace",
                "name": "functions",
                "description": "",
                "tools": [
                    {
                        "type": "function",
                        "name": "shell",
                        "description": "run a command",
                        "parameters": {"type": "object"},
                        "strict": False,
                    }
                ],
            }
        ],
    }
    assert kwargs["input"][1] == {
        "type": "message",
        "role": "developer",
        "content": [{"type": "input_text", "text": "system"}],
    }
    assert kwargs["input"][3]["type"] == "reasoning"
    assert kwargs["input"][3]["encrypted_content"] == "encrypted-reasoning"
    assert kwargs["input"][5] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "result",
    }
    assert kwargs["extra_body"]["client_metadata"]["turn_id"] == "turn-1"


def _turn_session(*, model: str) -> CodexTurnSession:
    return CodexTurnSession(
        model=model,
        identity=CodexTurnIdentity(
            installation_id="installation-1",
            session_id="session-1",
            thread_id="session-1",
            window_id="window-1",
            turn_id="turn-1",
            turn_started_at_unix_ms=1_000,
        ),
    )
