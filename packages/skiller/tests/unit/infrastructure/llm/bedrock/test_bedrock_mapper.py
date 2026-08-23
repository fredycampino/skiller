from __future__ import annotations

import pytest

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.infrastructure.llm.bedrock.bedrock_mapper import BedrockMapper

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


def test_bedrock_mapper_adds_cache_point_before_last_message() -> None:
    request = BedrockLLMRequest(
        messages=(LLMUserMessage("history"), LLMUserMessage("new")),
        model=_model("us.anthropic.claude-opus-4-6-v1", 200_000, max_output_tokens=4096),
    )

    kwargs = BedrockMapper().to_kwargs(request)

    assert kwargs["inferenceConfig"] == {"maxTokens": 4096}
    assert kwargs["messages"] == [
        {
            "role": "user",
            "content": [
                {"text": "history"},
                {"cachePoint": {"type": "default"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"text": "new"},
            ],
        },
    ]


def test_bedrock_mapper_groups_consecutive_tool_results() -> None:
    request = BedrockLLMRequest(
        messages=(
            LLMUserMessage("run tools"),
            LLMAssistantMessage(
                tool_calls=(
                    LLMToolCall(
                        id="tooluse_1",
                        function=LLMToolCallFunction(
                            name="shell",
                            arguments_json='{"command":"pwd"}',
                        ),
                    ),
                    LLMToolCall(
                        id="tooluse_2",
                        function=LLMToolCallFunction(
                            name="shell",
                            arguments_json='{"command":"whoami"}',
                        ),
                    ),
                )
            ),
            LLMToolMessage('{"ok":true}', tool_call_id="tooluse_1"),
            LLMToolMessage('{"ok":true}', tool_call_id="tooluse_2"),
        ),
        model=_model("us.anthropic.claude-opus-4-6-v1", 200_000, max_output_tokens=4096),
    )

    kwargs = BedrockMapper().to_kwargs(request)

    assert kwargs["messages"] == [
        {"role": "user", "content": [{"text": "run tools"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tooluse_1",
                        "name": "shell",
                        "input": {"command": "pwd"},
                    }
                },
                {
                    "toolUse": {
                        "toolUseId": "tooluse_2",
                        "name": "shell",
                        "input": {"command": "whoami"},
                    }
                },
                {"cachePoint": {"type": "default"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "tooluse_1",
                        "content": [{"text": '{"ok":true}'}],
                        "status": "success",
                    }
                },
                {
                    "toolResult": {
                        "toolUseId": "tooluse_2",
                        "content": [{"text": '{"ok":true}'}],
                        "status": "success",
                    }
                },
            ],
        },
    ]


def test_bedrock_mapper_omits_inference_config_when_model_has_no_limit() -> None:
    request = BedrockLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("us.anthropic.claude-opus-4-6-v1", 200_000),
    )

    kwargs = BedrockMapper().to_kwargs(request)

    assert "inferenceConfig" not in kwargs
