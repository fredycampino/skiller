from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.tool.tool_contract import ToolDefinition
from skiller.infrastructure.llm.mapper.llm_protocol_mapper import LLMProtocolMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import (
    LLMProviderUsage,
    LLMUsageMapper,
)


@dataclass(frozen=True)
class BedrockMapper(LLMProtocolMapper[BedrockLLMRequest, object]):
    usage_mapper: LLMUsageMapper

    def to_kwargs(self, request: BedrockLLMRequest) -> dict[str, object]:
        system, messages = _messages_to_payload(request.messages)
        payload: dict[str, object] = {
            "modelId": request.model.value,
            "messages": messages,
            "inferenceConfig": {"maxTokens": request.max_tokens},
        }
        if system:
            payload["system"] = system
        if request.tools:
            payload["toolConfig"] = {
                "tools": [_tool_definition_to_payload(tool) for tool in request.tools],
                "toolChoice": {"auto": {}},
            }
        return payload

    def to_response(
        self,
        raw_response: object,
        *,
        request: BedrockLLMRequest,
    ) -> LLMResponse:
        return _to_port_llm_response(
            raw_response,
            request=request,
            usage_mapper=self.usage_mapper,
        )


def _to_port_llm_response(
    response: object,
    *,
    request: BedrockLLMRequest,
    usage_mapper: LLMUsageMapper,
) -> LLMResponse:
    if not isinstance(response, Mapping):
        return LLMResponse(
            ok=False,
            model=request.model,
            error="Bedrock response must be a JSON object",
            error_code="invalid_response",
        )

    output = response.get("output")
    if not isinstance(output, Mapping):
        return LLMResponse(
            ok=False,
            model=request.model,
            error="Bedrock response missing output payload",
            error_code="missing_output",
        )
    message = output.get("message")
    if not isinstance(message, Mapping):
        return LLMResponse(
            ok=False,
            model=request.model,
            error="Bedrock response missing output message",
            error_code="missing_message",
        )

    content_blocks = message.get("content")
    if not isinstance(content_blocks, list):
        return LLMResponse(
            ok=False,
            model=request.model,
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

    provider_usage = _to_provider_usage(response.get("usage"))
    usage = usage_mapper.to_usage(provider_usage, request=request)
    finish_reason = response.get("stopReason")
    return LLMResponse(
        ok=True,
        model=request.model,
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
    if len(payload_messages) > 1:
        content = payload_messages[-2]["content"]
        if isinstance(content, list):
            content.append({"cachePoint": {"type": "default"}})
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


def _to_provider_usage(raw_usage: object) -> LLMProviderUsage | None:
    if not isinstance(raw_usage, Mapping):
        return None
    prompt_tokens = _optional_int(raw_usage.get("inputTokens"))
    cache_read_tokens = _optional_int(raw_usage.get("cacheReadInputTokens"))
    cache_write_tokens = _optional_int(raw_usage.get("cacheWriteInputTokens"))
    return LLMProviderUsage(
        prompt_tokens=_total_prompt_tokens(
            prompt_tokens=prompt_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        ),
        output_tokens=_optional_int(raw_usage.get("outputTokens")),
        total_tokens=_optional_int(raw_usage.get("totalTokens")),
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def _total_prompt_tokens(
    *,
    prompt_tokens: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
) -> int | None:
    if prompt_tokens is None:
        return None
    return prompt_tokens + (cache_read_tokens or 0) + (cache_write_tokens or 0)


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
