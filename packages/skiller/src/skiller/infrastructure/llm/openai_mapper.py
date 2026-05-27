from __future__ import annotations

import json
from collections.abc import Mapping

from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolChoice,
    LLMToolChoiceMode,
    LLMToolMessage,
    LLMUsage,
)
from skiller.domain.tool.tool_contract import ToolDefinition


def to_openai_kwargs(request: LLMRequest) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": request.model,
        "messages": [_message_to_payload(message) for message in request.messages],
    }
    if request.tools:
        payload["tools"] = [_tool_definition_to_payload(tool) for tool in request.tools]
    if request.tool_choice is not None:
        payload["tool_choice"] = _tool_choice_value(request.tool_choice)
    if request.response_format is not None:
        payload["response_format"] = _response_format_value(request.response_format)
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.parallel_tool_calls is not None:
        payload["parallel_tool_calls"] = request.parallel_tool_calls
    return payload


def to_port_llm_response(response: object, *, fallback_model: str) -> LLMResponse:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return LLMResponse(
            ok=False,
            error="OpenAI response missing choices",
            error_code="missing_choices",
        )

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, Mapping):
        message = first_choice.get("message")
    if message is None:
        return LLMResponse(
            ok=False,
            error="OpenAI response missing message payload",
            error_code="missing_message",
        )

    tool_calls = _to_port_tool_calls(getattr(message, "tool_calls", None))
    if not tool_calls and isinstance(message, Mapping):
        tool_calls = _to_port_tool_calls(message.get("tool_calls"))

    content = _to_port_content(getattr(message, "content", None))
    if content is None and isinstance(message, Mapping):
        content = _to_port_content(message.get("content"))

    response_model = getattr(response, "model", None)
    if response_model is None and isinstance(response, Mapping):
        response_model = response.get("model")

    finish_reason = getattr(first_choice, "finish_reason", None)
    if finish_reason is None and isinstance(first_choice, Mapping):
        finish_reason = first_choice.get("finish_reason")

    usage = _to_port_usage(getattr(response, "usage", None))
    if usage is None and isinstance(response, Mapping):
        usage = _to_port_usage(response.get("usage"))

    return LLMResponse(
        ok=True,
        content=content,
        model=_response_model(response_model, fallback_model=fallback_model),
        tool_calls=tool_calls,
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        usage=usage,
    )


def _response_model(response_model: object, *, fallback_model: str) -> str:
    if isinstance(response_model, str) and response_model.strip():
        return response_model
    return fallback_model


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


def _to_port_usage(raw_usage: object) -> LLMUsage | None:
    if raw_usage is None:
        return None
    return LLMUsage(
        prompt_tokens=_optional_int(_value(raw_usage, "prompt_tokens")),
        completion_tokens=_optional_int(_value(raw_usage, "completion_tokens")),
        total_tokens=_optional_int(_value(raw_usage, "total_tokens")),
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


def _tool_choice_value(tool_choice: LLMToolChoice) -> str | dict[str, object]:
    if tool_choice.mode in {LLMToolChoiceMode.AUTO, LLMToolChoiceMode.NONE}:
        return tool_choice.mode.value
    if tool_choice.tool_name is None:
        return tool_choice.mode.value
    return {
        "type": "function",
        "function": {"name": tool_choice.tool_name},
    }


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
