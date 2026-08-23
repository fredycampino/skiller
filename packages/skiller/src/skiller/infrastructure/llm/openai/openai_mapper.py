from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMResponse,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolChoiceMode,
    LLMToolMessage,
)
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.domain.tool.tool_contract import ToolDefinition
from skiller.infrastructure.llm.mapper.llm_protocol_mapper import LLMProtocolMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import (
    LLMProviderUsage,
    LLMUsageMapper,
)


@dataclass(frozen=True)
class OpenAIMapper(LLMProtocolMapper[OpenAILLMRequest, object]):
    usage_mapper: LLMUsageMapper
    extra_body: Mapping[str, object] | None = None

    def to_kwargs(self, request: OpenAILLMRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": request.model.value,
            "messages": [_message_to_payload(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = [_tool_definition_to_payload(tool) for tool in request.tools]
        payload["tool_choice"] = _tool_choice_value(request.tool_choice)
        if request.response_format is not None:
            payload["response_format"] = _response_format_value(request.response_format)
        payload["temperature"] = request.temperature
        if request.model.max_output_tokens is not None:
            payload["max_tokens"] = request.model.max_output_tokens
        payload["top_p"] = request.top_p
        payload["parallel_tool_calls"] = request.parallel_tool_calls
        if self.extra_body is not None:
            payload["extra_body"] = dict(self.extra_body)
        return payload

    def to_response(
        self,
        raw_response: object,
        *,
        request: OpenAILLMRequest,
    ) -> LLMResponse:
        choices = getattr(raw_response, "choices", None)
        if choices is None and isinstance(raw_response, Mapping):
            choices = raw_response.get("choices")
        if not isinstance(choices, list) or not choices:
            return LLMResponse(
                model=request.model,
                finish_type=LLMFinishType.ERROR_MISSING_CHOICES,
                error="OpenAI response missing choices",
                error_code="missing_choices",
            )

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None and isinstance(first_choice, Mapping):
            message = first_choice.get("message")
        if message is None:
            return LLMResponse(
                model=request.model,
                finish_type=LLMFinishType.ERROR_MISSING_MESSAGE,
                error="OpenAI response missing message payload",
                error_code="missing_message",
            )

        tool_calls = _to_port_tool_calls(getattr(message, "tool_calls", None))
        if not tool_calls and isinstance(message, Mapping):
            tool_calls = _to_port_tool_calls(message.get("tool_calls"))

        content = _to_port_content(getattr(message, "content", None))
        if content is None and isinstance(message, Mapping):
            content = _to_port_content(message.get("content"))

        finish_reason = getattr(first_choice, "finish_reason", None)
        if finish_reason is None and isinstance(first_choice, Mapping):
            finish_reason = first_choice.get("finish_reason")
        finish_type = _finish_type(
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            content=content,
            tool_calls=tool_calls,
        )
        error: str | None = None
        error_code: str | None = None
        if finish_type == LLMFinishType.INVALID_RESPONSE_LENGTH:
            error = "OpenAI response was truncated due to length"
            error_code = "response_length"
        elif finish_type == LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER:
            error = "OpenAI response was blocked by the content filter"
            error_code = "content_filter"
        elif finish_type == LLMFinishType.ERROR_MISSING_FINISH_REASON:
            error = "OpenAI response missing finish reason"
            error_code = "missing_finish_reason"
        elif finish_type == LLMFinishType.ERROR_MISSING_CONTENT:
            error = "OpenAI response missing content"
            error_code = "missing_content"
        elif finish_type == LLMFinishType.ERROR_MISSING_TOOL_CALLS:
            error = "OpenAI response missing tool calls"
            error_code = "missing_tool_calls"
        elif finish_type == LLMFinishType.ERROR_MALFORMED_RESPONSE:
            error = "OpenAI response has an inconsistent finish reason"
            error_code = "inconsistent_finish_reason"
        elif finish_type == LLMFinishType.UNKNOWN:
            error = "OpenAI response has an unknown finish reason"
            error_code = "unknown_finish_reason"

        provider_usage = _to_provider_usage(getattr(raw_response, "usage", None))
        if provider_usage is None and isinstance(raw_response, Mapping):
            provider_usage = _to_provider_usage(raw_response.get("usage"))
        usage = self.usage_mapper.to_usage(provider_usage, request=request)

        return LLMResponse(
            content=content,
            model=request.model,
            tool_calls=tool_calls,
            finish_type=finish_type,
            error=error,
            error_code=error_code,
            usage=usage,
        )


def _finish_type(
    *,
    finish_reason: str | None,
    content: str | None,
    tool_calls: tuple[LLMToolCall, ...],
) -> LLMFinishType:
    if finish_reason is None:
        return LLMFinishType.ERROR_MISSING_FINISH_REASON
    if finish_reason == "stop":
        if tool_calls:
            return LLMFinishType.ERROR_MALFORMED_RESPONSE
        if content is None or not content.strip():
            return LLMFinishType.ERROR_MISSING_CONTENT
        return LLMFinishType.STOP
    if finish_reason == "length":
        return LLMFinishType.INVALID_RESPONSE_LENGTH
    if finish_reason == "content_filter":
        return LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER
    if finish_reason == "function_call":
        if not tool_calls:
            return LLMFinishType.ERROR_MISSING_TOOL_CALLS
        return LLMFinishType.TOOL_CALLS
    if finish_reason == "tool_calls":
        if not tool_calls:
            return LLMFinishType.ERROR_MISSING_TOOL_CALLS
        return LLMFinishType.TOOL_CALLS
    return LLMFinishType.UNKNOWN


def _message_to_payload(message: LLMMessage) -> dict[str, object]:
    payload: dict[str, object] = {"role": message.role.value}
    payload["content"] = message.content
    if message.name is not None:
        payload["name"] = message.name
    if isinstance(message, LLMAssistantMessage) and message.tool_calls:
        payload["tool_calls"] = [
            _tool_call_to_payload(tool_call) for tool_call in message.tool_calls
        ]
    if isinstance(message, LLMToolMessage):
        payload["tool_call_id"] = message.tool_call_id
    return payload


def _to_port_tool_calls(raw_tool_calls: object) -> tuple[LLMToolCall, ...]:
    if not isinstance(raw_tool_calls, list):
        return ()

    parsed: list[LLMToolCall] = []
    for raw in raw_tool_calls:
        tool_call_id = getattr(raw, "id", None)
        if tool_call_id is None and isinstance(raw, Mapping):
            tool_call_id = raw.get("id")

        function = getattr(raw, "function", None)
        if function is None and isinstance(raw, Mapping):
            function = raw.get("function")

        function_name = getattr(function, "name", None)
        if function_name is None and isinstance(function, Mapping):
            function_name = function.get("name")

        function_arguments = getattr(function, "arguments", None)
        if function_arguments is None and isinstance(function, Mapping):
            function_arguments = function.get("arguments")

        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
            continue
        if not isinstance(function_name, str) or not function_name.strip():
            continue

        if isinstance(function_arguments, str):
            arguments_json = function_arguments
        else:
            arguments_json = json.dumps(
                function_arguments if function_arguments is not None else {},
                ensure_ascii=False,
            )

        parsed.append(
            LLMToolCall(
                id=tool_call_id.strip(),
                function=LLMToolCallFunction(
                    name=function_name.strip(),
                    arguments_json=arguments_json,
                ),
            )
        )
    return tuple(parsed)


def _to_port_content(raw_content: object) -> str | None:
    if raw_content is None:
        return None
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, (dict, list, int, float, bool)):
        return json.dumps(raw_content, ensure_ascii=False)
    return str(raw_content)


def _to_provider_usage(raw_usage: object) -> LLMProviderUsage | None:
    if raw_usage is None:
        return None
    return LLMProviderUsage(
        prompt_tokens=_optional_int(_value(raw_usage, "prompt_tokens")),
        output_tokens=_optional_int(_value(raw_usage, "completion_tokens")),
        total_tokens=_optional_int(_value(raw_usage, "total_tokens")),
        cache_read_tokens=_optional_int(
            _value(_value(raw_usage, "prompt_tokens_details"), "cached_tokens")
        ),
        cache_write_tokens=_optional_int(
            _value(_value(raw_usage, "prompt_tokens_details"), "cache_write_tokens")
        ),
    )


def _value(source: object, key: str) -> object:
    value = getattr(source, key, None)
    if value is None and isinstance(source, Mapping):
        return source.get(key)
    return value


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _tool_call_to_payload(tool_call: LLMToolCall) -> dict[str, object]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": _tool_call_function_to_payload(tool_call.function),
    }


def _tool_call_function_to_payload(
    tool_call_function: LLMToolCallFunction,
) -> dict[str, str]:
    return {
        "name": tool_call_function.name,
        "arguments": tool_call_function.arguments_json,
    }


def _tool_definition_to_payload(tool: ToolDefinition) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.schema().value),
        },
    }
    return payload


def _tool_choice_value(tool_choice: LLMToolChoiceMode) -> str:
    return tool_choice.value


def _response_format_value(response_format: LLMResponseFormat) -> dict[str, object]:
    payload: dict[str, object] = {"type": response_format.type.value}
    if response_format.type == LLMResponseFormatType.JSON_SCHEMA:
        json_schema: dict[str, object] = {}
        if response_format.json_schema_name is not None:
            json_schema["name"] = response_format.json_schema_name
        if response_format.json_schema is not None:
            json_schema["schema"] = dict(response_format.json_schema)
        if response_format.strict is not None:
            json_schema["strict"] = response_format.strict
        payload["json_schema"] = json_schema
    return payload
