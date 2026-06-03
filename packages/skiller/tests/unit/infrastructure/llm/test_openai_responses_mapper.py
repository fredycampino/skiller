from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.agent_llm_generation_model import LLMToolChoiceMode
from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexLLMModel,
    AgentMiniMaxLLMModel,
)
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm_request import MiniMaxLLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.openai_responses_mapper import (
    OpenAIResponsesStreamResult,
    to_openai_responses_kwargs,
    to_port_llm_response,
)

pytestmark = pytest.mark.unit


class _ShellTool(ToolDefinition[ToolRequest]):
    name = "shell"
    description = "run command"

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {"command": {"type": "string"}},
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        _ = input
        return ToolRequestResult.valid(ToolRequest())


class _ResponseWithBrokenOutputText:
    model = "gpt-5.4"
    status = "completed"
    output = None
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )

    @property
    def output_text(self) -> str:
        raise TypeError("'NoneType' object is not iterable")


def test_to_openai_responses_kwargs_maps_request_to_responses_payload() -> None:
    request = MiniMaxLLMRequest(
        messages=(
            LLMSystemMessage("system"),
            LLMUserMessage("hello"),
            LLMAssistantMessage(
                content="I will run it",
                tool_calls=(
                    LLMToolCall(
                        id="call_1",
                        function=LLMToolCallFunction(
                            name="shell",
                            arguments_json='{"command":"pwd"}',
                        ),
                    ),
                ),
            ),
            LLMToolMessage("pwd output", tool_call_id="call_1"),
        ),
        model=AgentMiniMaxLLMModel.M2_7,
        tools=(_ShellTool(),),
        tool_choice=LLMToolChoiceMode.REQUIRED,
        response_format=LLMResponseFormat(
            type=LLMResponseFormatType.JSON_SCHEMA,
            json_schema_name="result",
            json_schema={"type": "object"},
            strict=True,
        ),
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        parallel_tool_calls=True,
    )

    kwargs = to_openai_responses_kwargs(request)

    assert kwargs == {
        "model": "MiniMax-M2.7",
        "instructions": "system",
        "input": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "I will run it"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "shell",
                "arguments": '{"command":"pwd"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "pwd output",
            },
        ],
        "store": False,
        "tools": [
            {
                "type": "function",
                "name": "shell",
                "description": "run command",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
            }
        ],
        "tool_choice": "required",
        "text": {
            "format": {
                "type": "json_schema",
                "name": "result",
                "schema": {"type": "object"},
                "strict": True,
            }
        },
        "temperature": 0.2,
        "max_output_tokens": 128,
        "top_p": 0.9,
        "parallel_tool_calls": True,
    }


def test_to_port_llm_response_maps_final_response_to_port_response() -> None:
    stream_result = OpenAIResponsesStreamResult(
        response=SimpleNamespace(
            model="gpt-5.4",
            status="completed",
            output_text="hello",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            ),
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    name="shell",
                    arguments='{"command":"pwd"}',
                )
            ],
        )
    )

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.ok is True
    assert result.content == "hello"
    assert result.model == AgentCodexLLMModel.GPT_5_4
    assert result.finish_reason == "completed"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"pwd"}',
            ),
        ),
    )


def test_to_port_llm_response_prefers_streamed_text() -> None:
    stream_result = OpenAIResponsesStreamResult(
        response=SimpleNamespace(
            model="gpt-5.4",
            status="completed",
            output_text="final text",
            output=[],
        ),
        text_deltas=("streamed", " text"),
    )

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.content == "streamed text"


def test_to_port_llm_response_reads_text_from_message_output() -> None:
    stream_result = OpenAIResponsesStreamResult(
        response={
            "model": "gpt-5.4",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "hello"},
                        {"type": "output_text", "text": " world"},
                    ],
                }
            ],
        }
    )

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.content == "hello world"


def test_to_port_llm_response_uses_streamed_output_items_when_final_output_is_empty() -> None:
    stream_result = OpenAIResponsesStreamResult(
        response=SimpleNamespace(model="gpt-5.4", status="completed", output=[]),
        output_items=(
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "shell",
                "arguments": {"command": "pwd"},
            },
        ),
    )

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command": "pwd"}',
            ),
        ),
    )


def test_to_port_llm_response_tolerates_codex_output_text_with_null_output() -> None:
    stream_result = OpenAIResponsesStreamResult(
        response=_ResponseWithBrokenOutputText(),
        output_items=(
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "shell",
                "arguments": {"command": "pwd"},
            },
        ),
    )

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.ok is True
    assert result.content is None
    assert result.usage is not None
    assert result.usage.total_tokens == 15
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command": "pwd"}',
            ),
        ),
    )
