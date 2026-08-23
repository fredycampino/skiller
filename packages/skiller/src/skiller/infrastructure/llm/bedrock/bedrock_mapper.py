from __future__ import annotations

import json

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMToolMessage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.tool.tool_contract import ToolDefinition


class BedrockMapper:
    def to_kwargs(self, request: BedrockLLMRequest) -> dict[str, object]:
        system, messages = _messages_to_payload(request.messages)
        payload: dict[str, object] = {
            "modelId": request.model.value,
            "messages": messages,
        }
        if request.model.max_output_tokens is not None:
            payload["inferenceConfig"] = {"maxTokens": request.model.max_output_tokens}
        if system:
            payload["system"] = system
        if request.tools:
            payload["toolConfig"] = {
                "tools": [_tool_definition_to_payload(tool) for tool in request.tools],
                "toolChoice": {"auto": {}},
            }
        return payload


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
