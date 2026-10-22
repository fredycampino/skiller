from __future__ import annotations

import copy

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
from skiller.infrastructure.llm.bedrock.bedrock_tool_continuation import BedrockToolContinuation
from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseReasoningTextContentBlock,
    ConverseRedactedReasoningContentBlock,
    ConverseTextContentBlock,
    ConverseToolUseContentBlock,
)

pytestmark = pytest.mark.unit


def _assistant(identifier: str) -> LLMAssistantMessage:
    return LLMAssistantMessage(
        content="Reading.",
        tool_calls=(
            LLMToolCall(
                id=identifier,
                function=LLMToolCallFunction(
                    name="files",
                    arguments_json='{"path":"order.json"}',
                ),
            ),
        ),
    )


def _request(messages: tuple) -> BedrockLLMRequest:
    return BedrockLLMRequest(
        messages=messages,
        model=LLMModelDefinition(
            model="test", context_window_tokens=200_000, max_output_tokens=None
        ),
    )


def _blocks(identifier: str) -> tuple:
    return (
        ConverseReasoningTextContentBlock(text="original", signature="signed"),
        ConverseRedactedReasoningContentBlock(data=b"opaque"),
        ConverseTextContentBlock(text="Reading."),
        ConverseToolUseContentBlock(
            tool_use_id=identifier,
            name="files",
            input={"path": "order.json"},
        ),
    )


def test_three_continuations_extend_only_stable_prefix() -> None:
    continuation = BedrockToolContinuation()
    mapper = BedrockMapper()
    messages = (LLMUserMessage("Review"),)
    previous_prefix = []
    for number in range(3):
        identifier = f"call_{number}"
        continuation.record("test", _blocks(identifier))
        messages += (_assistant(identifier), LLMToolMessage("result", tool_call_id=identifier))
        request = _request(messages)
        kwargs = mapper.to_kwargs(request)
        continuation.restore(request, kwargs)
        payload = kwargs["messages"]
        cache_index = len(payload) - 3
        assert payload[cache_index]["content"][-1] == {"cachePoint": {"type": "default"}}
        assert payload[-2]["content"] == [
            {"reasoningContent": {"reasoningText": {"text": "original", "signature": "signed"}}},
            {"reasoningContent": {"redactedContent": b"opaque"}},
            {"text": "Reading."},
            {
                "toolUse": {
                    "toolUseId": identifier,
                    "name": "files",
                    "input": {"path": "order.json"},
                }
            },
        ]
        prefix = copy.deepcopy(payload[: cache_index + 1])
        prefix[-1]["content"].pop()
        assert prefix[: len(previous_prefix)] == previous_prefix
        assert all(
            "reasoningContent" not in block for message in prefix for block in message["content"]
        )
        previous_prefix = prefix
        continuation.complete(request)
        assert not continuation.pending


def test_restore_preserves_response_for_retry_and_does_not_match_other_calls() -> None:
    continuation = BedrockToolContinuation()
    continuation.record("test", _blocks("call_1"))
    for identifier in ("other", "call_1", "call_1"):
        request = _request(
            (
                LLMUserMessage("Review"),
                _assistant(identifier),
                LLMToolMessage("result", tool_call_id=identifier),
            )
        )
        kwargs = BedrockMapper().to_kwargs(request)
        continuation.restore(request, kwargs)
        has_reasoning = "reasoningContent" in kwargs["messages"][-2]["content"][0]
        assert has_reasoning == (identifier == "call_1")
    assert len(continuation.pending) == 1
