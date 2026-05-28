from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMModel,
)
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMResponseFormat,
    LLMResponseFormatType,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolChoice,
    LLMToolChoiceMode,
    LLMToolMessage,
    LLMUsage,
)
from skiller.domain.tool.tool_contract import ToolDefinition


@dataclass(frozen=True)
class OpenAIResponsesStreamResult:
    response: object | None
    text_deltas: tuple[object, ...] = ()
    output_items: tuple[object, ...] = ()


def to_openai_responses_kwargs(
    request: LLMRequest,
) -> dict[str, object]:
    instructions: list[str] = []
    input_items: list[dict[str, object]] = []

    for message in request.messages:
        if isinstance(message, LLMSystemMessage):
            instructions.append(message.content)
            continue

        input_items.extend(_message_to_input_items(message))

    payload: dict[str, object] = {
        "model": request.model.value,
        "instructions": "\n\n".join(instructions),
        "input": input_items,
        "store": False,
    }
    if request.tools:
        payload["tools"] = [_tool_definition_to_payload(tool) for tool in request.tools]
    if request.tool_choice is not None:
        payload["tool_choice"] = _tool_choice_value(request.tool_choice)
    if request.response_format is not None:
        payload["text"] = {"format": _response_format_value(request.response_format)}
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_output_tokens"] = request.max_tokens
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.parallel_tool_calls is not None:
        payload["parallel_tool_calls"] = request.parallel_tool_calls
    return payload


def to_port_llm_response(
    stream_result: OpenAIResponsesStreamResult,
    *,
    fallback_model: AgentLLMModel,
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

    response_model = _read_response_field(stream_result.response, "model")
    model = fallback_model
    if response_model == fallback_model.value:
        model = fallback_model

    status = _read_response_field(stream_result.response, "status")
    finish_reason = status if isinstance(status, str) and status else None
    usage = _to_port_usage(_read_response_field(stream_result.response, "usage"))

    return LLMResponse(
        ok=True,
        content=content,
        model=model,
        tool_calls=_to_port_tool_calls(output_items),
        finish_reason=finish_reason,
        usage=usage,
    )


def _message_to_input_items(message: LLMMessage) -> list[dict[str, object]]:
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


def _tool_definition_to_payload(tool: ToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": dict(tool.schema().value),
    }


def _tool_choice_value(tool_choice: LLMToolChoice) -> str | dict[str, object]:
    if tool_choice.mode in {LLMToolChoiceMode.AUTO, LLMToolChoiceMode.NONE}:
        return tool_choice.mode.value
    if tool_choice.tool_name is None:
        return tool_choice.mode.value
    return {
        "type": "function",
        "name": tool_choice.tool_name,
    }


def _response_format_value(response_format: LLMResponseFormat) -> dict[str, object]:
    payload: dict[str, object] = {"type": response_format.type.value}
    if response_format.type == LLMResponseFormatType.JSON_SCHEMA:
        if response_format.json_schema_name is not None:
            payload["name"] = response_format.json_schema_name
        if response_format.json_schema is not None:
            payload["schema"] = dict(response_format.json_schema)
        if response_format.strict is not None:
            payload["strict"] = response_format.strict
    return payload


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


def _to_port_usage(raw_usage: object) -> LLMUsage | None:
    if raw_usage is None:
        return None
    return LLMUsage(
        prompt_tokens=_optional_int(_read_response_field(raw_usage, "input_tokens")),
        completion_tokens=_optional_int(_read_response_field(raw_usage, "output_tokens")),
        total_tokens=_optional_int(_read_response_field(raw_usage, "total_tokens")),
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
