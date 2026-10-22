from __future__ import annotations

import json

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMToolMessage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.tool.tool_contract import ToolDefinition
from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseContentBlock,
    ConverseReasoningTextContentBlock,
    ConverseRedactedReasoningContentBlock,
    ConverseTextContentBlock,
)


class BedrockMapper:
    def to_kwargs(self, request: BedrockLLMRequest) -> dict[str, object]:
        system, messages = _messages_to_payload(request.messages)
        payload: dict[str, object] = {
            "modelId": request.model.value,
            "messages": messages,
        }
        if "anthropic" in request.model.value.split("."):
            payload["additionalModelRequestFields"] = _anthropic_thinking_fields(request)
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
    cache_index = len(payload_messages) - 2
    if messages and isinstance(messages[-1], LLMToolMessage):
        # Keep the latest assistant/tool-result exchange outside the stable prefix.
        cache_index -= 1
    if cache_index >= 0:
        content = payload_messages[cache_index]["content"]
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


def response_content_to_payload(
    blocks: tuple[ConverseContentBlock, ...],
) -> list[dict[str, object]]:
    content: list[dict[str, object]] = []
    for block in blocks:
        if isinstance(block, ConverseReasoningTextContentBlock):
            content.append(
                {
                    "reasoningContent": {
                        "reasoningText": {
                            "text": block.text,
                            "signature": block.signature,
                        }
                    }
                }
            )
        elif isinstance(block, ConverseRedactedReasoningContentBlock):
            content.append({"reasoningContent": {"redactedContent": block.data}})
        elif isinstance(block, ConverseTextContentBlock):
            content.append({"text": block.text})
        else:
            content.append(
                {
                    "toolUse": {
                        "toolUseId": block.tool_use_id,
                        "name": block.name,
                        "input": block.input,
                    }
                }
            )
    return content


def _anthropic_thinking_fields(request: BedrockLLMRequest) -> dict[str, object]:
    model = request.model.value.split("anthropic.", 1)[1]
    adaptive_only = model in {
        "claude-opus-5-5",
        "claude-fable-5",
        "claude-fable-5-1",
    }
    if request.effort is None:
        if adaptive_only:
            return {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}
        return {"thinking": {"type": "disabled"}}

    effort = ("low", "medium", "high", "xhigh", "max")[request.effort - 1]
    if effort == "xhigh" and model in {"claude-opus-4-6-v1", "claude-sonnet-4-6"}:
        effort = "high"
    return {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort}}
