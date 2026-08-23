from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolChoiceMode,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.openai.openai_mapper import (
    OpenAIMapper,
)

pytestmark = pytest.mark.unit


def _model(
    value: str,
    context_window_tokens: int,
    *,
    max_output_tokens: int | None = None,
) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=value,
        context_window_tokens=context_window_tokens,
        max_output_tokens=max_output_tokens,
    )


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
    request = OpenAILLMRequest(
        messages=(
            LLMSystemMessage("system"),
            LLMUserMessage("hello", name="tester"),
        ),
        model=_model("kimi-k3", 256_000, max_output_tokens=128),
        tools=(_ShellTool(),),
        tool_choice=LLMToolChoiceMode.REQUIRED,
        response_format=LLMResponseFormat(
            type=LLMResponseFormatType.JSON_SCHEMA,
            json_schema_name="result",
            json_schema={"type": "object"},
            strict=True,
        ),
        temperature=0.2,
        top_p=0.9,
        parallel_tool_calls=True,
    )

    kwargs = OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()).to_kwargs(request)

    assert kwargs == {
        "model": "kimi-k3",
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
        "tool_choice": "required",
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


def test_openai_mapper_adds_extra_body() -> None:
    request = OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("kimi-k3", 256_000),
        tool_choice=LLMToolChoiceMode.AUTO,
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
    )
    mapper = OpenAIMapper(
        usage_mapper=DefaultLLMUsageMapper(),
        extra_body={"reasoning_split": True},
    )

    kwargs = mapper.to_kwargs(request)

    assert kwargs["extra_body"] == {"reasoning_split": True}


def test_openai_mapper_omits_max_tokens_when_model_has_no_limit() -> None:
    request = OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("kimi-k3", 256_000),
        tool_choice=LLMToolChoiceMode.AUTO,
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
    )

    kwargs = OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()).to_kwargs(request)

    assert "max_tokens" not in kwargs


def test_openai_mapper_maps_response_to_port_response() -> None:
    response = SimpleNamespace(
        model="gpt-5.4",
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=25,
            total_tokens=125,
            prompt_tokens_details=SimpleNamespace(
                cached_tokens=80,
                cache_write_tokens=20,
            ),
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

    result = OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()).to_response(
        response,
        request=OpenAILLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=_model("kimi-k3", 256_000),
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=1,
            top_p=1,
            parallel_tool_calls=True,
        ),
    )

    assert result.finish_type == LLMFinishType.TOOL_CALLS
    assert result.model == _model("kimi-k3", 256_000)
    assert result.content is None
    assert result.usage is not None
    assert result.usage.prompt_tokens == 100
    assert result.usage.estimated_system_tokens == 0
    assert result.usage.output_tokens == 25
    assert result.usage.total_tokens == 125
    assert result.usage.cache_read_tokens == 80
    assert result.usage.cache_write_tokens == 20
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"git status"}',
            ),
        ),
    )


def test_openai_mapper_maps_dict_usage_to_port_response() -> None:
    request = OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("kimi-k3", 256_000),
        tool_choice=LLMToolChoiceMode.AUTO,
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
    )
    result = OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()).to_response(
        {
            "model": "kimi-k3",
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
        request=request,
    )

    assert result.finish_type == LLMFinishType.STOP
    assert result.model == _model("kimi-k3", 256_000)
    assert result.content == "Hello"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 42
    assert result.usage.output_tokens == 38
    assert result.usage.total_tokens == 80
