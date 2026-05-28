from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexLLMModel,
    AgentMiniMaxLLMModel,
)
from skiller.domain.agent.llm_model import (
    LLMRequest,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
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
from skiller.infrastructure.llm.openai_mapper import (
    to_openai_kwargs,
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


def test_to_openai_kwargs_maps_typed_request_to_sdk_kwargs() -> None:
    request = LLMRequest(
        messages=(
            LLMSystemMessage("system"),
            LLMUserMessage("hello", name="tester"),
        ),
        model=AgentCodexLLMModel.GPT_5_4,
        tools=(
            _ShellTool(),
        ),
        tool_choice=LLMToolChoice.tool("shell"),
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

    kwargs = to_openai_kwargs(request)

    assert kwargs == {
        "model": "gpt-5.4",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello", "name": "tester"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "run command",
                    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "shell"}},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "result",
                "schema": {"type": "object"},
                "strict": True,
            },
        },
        "temperature": 0.2,
        "max_tokens": 128,
        "top_p": 0.9,
        "parallel_tool_calls": True,
    }


def test_to_port_llm_response_maps_openai_payload_to_port_response() -> None:
    response = SimpleNamespace(
        model="gpt-5.4",
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=25,
            total_tokens=125,
        ),
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="shell",
                                arguments='{"command":"git status"}',
                            ),
                        )
                    ],
                ),
            )
        ],
    )

    result = to_port_llm_response(
        response,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.ok is True
    assert result.model == AgentCodexLLMModel.GPT_5_4
    assert result.finish_reason == "tool_calls"
    assert result.content is None
    assert result.usage is not None
    assert result.usage.prompt_tokens == 100
    assert result.usage.completion_tokens == 25
    assert result.usage.total_tokens == 125
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"git status"}',
            ),
        ),
    )


def test_to_port_llm_response_maps_dict_usage_to_port_response() -> None:
    result = to_port_llm_response(
        {
            "model": "MiniMax-M2.7",
            "usage": {
                "prompt_tokens": 42,
                "completion_tokens": 38,
                "total_tokens": 80,
            },
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": "Hello",
                    },
                }
            ],
        },
        fallback_model=AgentMiniMaxLLMModel.M2_7,
    )

    assert result.ok is True
    assert result.model == AgentMiniMaxLLMModel.M2_7
    assert result.content == "Hello"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 42
    assert result.usage.completion_tokens == 38
    assert result.usage.total_tokens == 80
