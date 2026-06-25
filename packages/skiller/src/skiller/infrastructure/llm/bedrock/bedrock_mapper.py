from __future__ import annotations

import json
from collections.abc import Mapping

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUsage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_registry import AgentLLMModel
from skiller.domain.tool.tool_contract import ToolDefinition


def to_bedrock_kwargs(
    request: BedrockLLMRequest,
    *,
    max_tokens: int,
    temperature: float,
) -> dict[str, object]:
    system, messages = _messages_to_payload(request.messages)
    payload: dict[str, object] = {
        "modelId": request.model.value,
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        payload["system"] = system
    if request.tools:
        payload["toolConfig"] = {
            "tools": [_tool_definition_to_payload(tool) for tool in request.tools],
            "toolChoice": {"auto": {}},
        }
    return payload


def to_port_llm_response(
    response: object,
    *,
    fallback_model: AgentLLMModel,
) -> LLMResponse:
    if not isinstance(response, Mapping):
        return LLMResponse(
            ok=False,
            model=fallback_model,
            error="Bedrock response must be a JSON object",
            error_code="invalid_response",
        )

    output = response.get("output")
    if not isinstance(output, Mapping):
        return LLMResponse(
            ok=False,
            model=fallback_model,
            error="Bedrock response missing output payload",
            error_code="missing_output",
        )
    message = output.get("message")
    if not isinstance(message, Mapping):
        return LLMResponse(
            ok=False,
            model=fallback_model,
            error="Bedrock response missing output message",
            error_code="missing_message",
        )

    content_blocks = message.get("content")
    if not isinstance(content_blocks, list):
        return LLMResponse(
            ok=False,
            model=fallback_model,
            error="Bedrock response message content must be a list",
            error_code="invalid_content",
        )

    text_parts: list[str] = []
    tool_calls: list[LLMToolCall] = []
    for block in content_blocks:
        if not isinstance(block, Mapping):
            continue
        text = block.get("text")
        if isinstance(text, str):
            text_parts.append(text)
            continue
        tool_use = block.get("toolUse")
        if not isinstance(tool_use, Mapping):
            continue
        tool_use_id = tool_use.get("toolUseId")
        name = tool_use.get("name")
        if not isinstance(tool_use_id, str) or not tool_use_id.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        arguments_json = json.dumps(
            tool_use.get("input", {}),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        tool_calls.append(
            LLMToolCall(
                id=tool_use_id.strip(),
                function=LLMToolCallFunction(name=name.strip(), arguments_json=arguments_json),
            )
        )

    usage = _to_usage(response.get("usage"))
    finish_reason = response.get("stopReason")
    return LLMResponse(
        ok=True,
        model=fallback_model,
        content="".join(text_parts) if text_parts else None,
        tool_calls=tuple(tool_calls),
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        usage=usage,
    )


def _messages_to_payload(
    messages: tuple[LLMMessage, ...],
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    system: list[dict[str, str]] = []
    payload_messages: list[dict[str, object]] = []
    pending_tool_results: list[dict[str, object]] = []

    def flush_tool_results() -> None:
        if not pending_tool_results:
            return
        payload_messages.append({"role": "user", "content": list(pending_tool_results)})
        pending_tool_results.clear()

    for message in messages:
        role = message.role.value
        if role == "system":
            system.append({"text": message.content})
            continue
        if isinstance(message, LLMToolMessage):
            pending_tool_results.append(
                {
                    "toolResult": {
                        "toolUseId": message.tool_call_id,
                        "content": [{"text": message.content}],
                        "status": "success",
                    }
                }
            )
            continue
        flush_tool_results()
        if isinstance(message, LLMAssistantMessage) and message.tool_calls:
            content: list[dict[str, object]] = []
            if message.content:
                content.append({"text": message.content})
            for tool_call in message.tool_calls:
                content.append(
                    {
                        "toolUse": {
                            "toolUseId": tool_call.id,
                            "name": tool_call.function.name,
                            "input": _tool_input(tool_call.function.arguments_json),
                        }
                    }
                )
            payload_messages.append({"role": "assistant", "content": content})
            continue
        payload_messages.append({"role": role, "content": [{"text": message.content}]})
    flush_tool_results()
    return system, payload_messages


def _tool_input(arguments_json: str) -> dict[str, object]:
    try:
        parsed = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {"raw_arguments": arguments_json}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _tool_definition_to_payload(tool: ToolDefinition) -> dict[str, object]:
    return {
        "toolSpec": {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": {
                "json": dict(tool.schema().value),
            },
        }
    }


def _to_usage(raw_usage: object) -> LLMUsage | None:
    if not isinstance(raw_usage, Mapping):
        return None
    return LLMUsage(
        prompt_tokens=_optional_int(raw_usage.get("inputTokens")),
        completion_tokens=_optional_int(raw_usage.get("outputTokens")),
        total_tokens=_optional_int(raw_usage.get("totalTokens")),
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
