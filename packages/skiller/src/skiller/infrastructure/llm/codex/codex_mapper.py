from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolMessage,
)
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.tool.tool_contract import ToolDefinition
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilities,
    CodexModelCapabilitiesResolver,
    CodexResponsesProtocol,
)
from skiller.infrastructure.llm.codex.codex_turn_session import CodexTurnSession


@dataclass(frozen=True)
class CodexMapper:
    capabilities_resolver: CodexModelCapabilitiesResolver
    responses_mapper: CodexRequestPayloadMapper
    responses_lite_mapper: CodexRequestPayloadMapper

    def capabilities(self, request: CodexLLMRequest) -> CodexModelCapabilities:
        return self.capabilities_resolver.resolve(request.model.value)

    def to_kwargs(
        self,
        request: CodexLLMRequest,
        *,
        capabilities: CodexModelCapabilities,
        turn_session: CodexTurnSession,
    ) -> dict[str, object]:
        if capabilities.protocol == CodexResponsesProtocol.LITE:
            return self.responses_lite_mapper.to_kwargs(
                request,
                turn_session=turn_session,
            )
        return self.responses_mapper.to_kwargs(
            request,
            turn_session=turn_session,
        )


class CodexRequestPayloadMapper(Protocol):
    def to_kwargs(
        self,
        request: CodexLLMRequest,
        *,
        turn_session: CodexTurnSession,
    ) -> dict[str, object]: ...


def to_codex_prompt_payload(
    messages: tuple[LLMMessage, ...],
) -> tuple[str, list[dict[str, object]]]:
    instructions: list[str] = []
    input_items: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message, LLMSystemMessage):
            instructions.append(message.content)
            continue

        input_items.extend(message_to_codex_input_items(message))

    return "\n\n".join(instructions), input_items


def to_codex_tool_payload(tool: ToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": dict(tool.schema().value),
    }


def to_codex_response_format_payload(
    response_format: LLMResponseFormat,
) -> dict[str, object]:
    payload: dict[str, object] = {"type": response_format.type.value}
    if response_format.type == LLMResponseFormatType.JSON_SCHEMA:
        if response_format.json_schema_name is not None:
            payload["name"] = response_format.json_schema_name
        if response_format.json_schema is not None:
            payload["schema"] = dict(response_format.json_schema)
        if response_format.strict is not None:
            payload["strict"] = response_format.strict
    return payload


def message_to_codex_input_items(message: LLMMessage) -> list[dict[str, object]]:
    if isinstance(message, LLMToolMessage):
        return [
            {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": message.content,
            }
        ]

    if isinstance(message, LLMAssistantMessage):
        input_items: list[dict[str, object]] = []
        if message.content is not None:
            input_items.append(
                {
                    "role": message.role.value,
                    "content": message.content,
                }
            )
        for tool_call in message.tool_calls:
            input_items.append(_tool_call_to_input_item(tool_call))
        return input_items

    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
    ]


def _tool_call_to_input_item(tool_call: LLMToolCall) -> dict[str, object]:
    return {
        "type": "function_call",
        "call_id": tool_call.id,
        "name": tool_call.function.name,
        "arguments": tool_call.function.arguments_json,
    }
