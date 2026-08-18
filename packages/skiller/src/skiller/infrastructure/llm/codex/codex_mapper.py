from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMResponse,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
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
from skiller.infrastructure.llm.mapper.llm_usage_mapper import (
    LLMProviderUsage,
    LLMUsageMapper,
)


@dataclass(frozen=True)
class CodexStreamResult:
    response: object | None
    text_deltas: tuple[object, ...] = ()
    output_items: tuple[object, ...] = ()


@dataclass(frozen=True)
class CodexMapper:
    usage_mapper: LLMUsageMapper
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

    def to_response(
        self,
        raw_response: CodexStreamResult,
        *,
        request: CodexLLMRequest,
    ) -> LLMResponse:
        return _to_port_llm_response(
            raw_response,
            request=request,
            usage_mapper=self.usage_mapper,
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


def _to_port_llm_response(
    stream_result: CodexStreamResult,
    *,
    request: CodexLLMRequest,
    usage_mapper: LLMUsageMapper,
) -> LLMResponse:
    raw_output_items = _read_response_field(stream_result.response, "output")
    output_items = raw_output_items if isinstance(raw_output_items, list) else []
    if not output_items:
        output_items = list(stream_result.output_items)

    streamed_text = "".join(delta for delta in stream_result.text_deltas if isinstance(delta, str))
    content = streamed_text or None

    if content is None:
        output_text = _read_response_field(stream_result.response, "output_text")
        if isinstance(output_text, str) and output_text:
            content = output_text

    if content is None:
        text_parts: list[str] = []
        for output_item in output_items:
            if _read_response_field(output_item, "type") != "message":
                continue

            message_content = _read_response_field(output_item, "content")
            if not isinstance(message_content, list):
                continue

            for content_part in message_content:
                if _read_response_field(content_part, "type") not in {"output_text", "text"}:
                    continue

                text = _read_response_field(content_part, "text")
                if isinstance(text, str):
                    text_parts.append(text)

        message_text = "".join(text_parts)
        content = message_text or None

    status = _read_response_field(stream_result.response, "status")
    finish_reason = status if isinstance(status, str) and status else None
    provider_usage = _to_provider_usage(
        _read_response_field(stream_result.response, "usage")
    )
    usage = usage_mapper.to_usage(provider_usage, request=request)

    return LLMResponse(
        ok=True,
        content=content,
        model=request.model,
        tool_calls=_to_port_tool_calls(output_items),
        finish_reason=finish_reason,
        usage=usage,
    )


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


def _to_port_tool_calls(output_items: list[object]) -> tuple[LLMToolCall, ...]:
    tool_calls: list[LLMToolCall] = []
    for output_item in output_items:
        if _read_response_field(output_item, "type") != "function_call":
            continue

        call_id = _read_response_field(output_item, "call_id")
        name = _read_response_field(output_item, "name")
        arguments = _read_response_field(output_item, "arguments")
        if not isinstance(call_id, str) or not isinstance(name, str):
            continue

        arguments_json = _arguments_json(arguments)
        tool_calls.append(
            LLMToolCall(
                id=call_id,
                function=LLMToolCallFunction(
                    name=name,
                    arguments_json=arguments_json,
                ),
            )
        )
    return tuple(tool_calls)


def _arguments_json(arguments: object) -> str:
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments if arguments is not None else {}, ensure_ascii=False)


def _to_provider_usage(raw_usage: object) -> LLMProviderUsage | None:
    if raw_usage is None:
        return None
    return LLMProviderUsage(
        prompt_tokens=_optional_int(_read_response_field(raw_usage, "input_tokens")),
        output_tokens=_optional_int(_read_response_field(raw_usage, "output_tokens")),
        total_tokens=_optional_int(_read_response_field(raw_usage, "total_tokens")),
        cache_read_tokens=_optional_int(
            _read_response_field(
                _read_response_field(raw_usage, "input_tokens_details"),
                "cached_tokens",
            )
        ),
        cache_write_tokens=_optional_int(
            _read_response_field(
                _read_response_field(raw_usage, "input_tokens_details"),
                "cache_write_tokens",
            )
        ),
    )


def _read_response_field(source: object, key: str) -> object:
    try:
        value = getattr(source, key, None)
    except TypeError:
        # Codex can finish with output=None while SDK properties still try to
        # iterate output, for example response.output_text.
        value = None
    if value is None and isinstance(source, Mapping):
        return source.get(key)
    return value


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
