from __future__ import annotations

import copy
from dataclasses import dataclass, field

from skiller.domain.agent.llm.model import LLMAssistantMessage, LLMToolMessage
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.infrastructure.llm.bedrock.bedrock_mapper import response_content_to_payload
from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseContentBlock,
    ConverseToolUseContentBlock,
)


@dataclass
class BedrockToolContinuation:
    pending: dict[tuple[str, tuple[str, ...]], tuple[ConverseContentBlock, ...]] = field(
        default_factory=dict
    )

    def restore(self, request: BedrockLLMRequest, kwargs: dict[str, object]) -> None:
        if not request.messages or not isinstance(request.messages[-1], LLMToolMessage):
            return
        assistant = next(
            (
                message
                for message in reversed(request.messages)
                if isinstance(message, LLMAssistantMessage)
            ),
            None,
        )
        if assistant is None:
            return
        ids = tuple(call.id for call in assistant.tool_calls)
        content = self.pending.get((request.model.value, ids))
        if content is None:
            return
        # The mapper groups trailing tool results into one user message.
        kwargs["messages"][-2]["content"] = response_content_to_payload(copy.deepcopy(content))

    def complete(self, request: BedrockLLMRequest) -> None:
        assistant = next(
            (
                message
                for message in reversed(request.messages)
                if isinstance(message, LLMAssistantMessage)
            ),
            None,
        )
        if assistant is not None:
            ids = tuple(call.id for call in assistant.tool_calls)
            self.pending.pop((request.model.value, ids), None)

    def record(self, model: str, content: tuple[ConverseContentBlock, ...]) -> None:
        ids = tuple(
            block.tool_use_id for block in content if isinstance(block, ConverseToolUseContentBlock)
        )
        if ids:
            self.pending[(model, ids)] = copy.deepcopy(content)
