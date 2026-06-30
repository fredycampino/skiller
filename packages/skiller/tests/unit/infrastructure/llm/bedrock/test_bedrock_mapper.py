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
from skiller.domain.agent.llm.provider_registry import AgentBedrockLLMModel
from skiller.infrastructure.llm.bedrock.bedrock_mapper import to_bedrock_kwargs

pytestmark = pytest.mark.unit


def test_to_bedrock_kwargs_groups_consecutive_tool_results() -> None:
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
        model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
        max_tokens=4096,
    )

    kwargs = to_bedrock_kwargs(request, max_tokens=4096)

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
