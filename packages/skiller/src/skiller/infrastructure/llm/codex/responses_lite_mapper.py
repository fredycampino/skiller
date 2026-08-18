from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMSystemMessage,
)
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_mapper import (
    message_to_codex_input_items,
    to_codex_response_format_payload,
    to_codex_tool_payload,
)
from skiller.infrastructure.llm.codex.codex_reasoning import (
    CODEX_DEFAULT_REASONING_EFFORT,
)
from skiller.infrastructure.llm.codex.codex_turn_session import (
    CODEX_TURN_STATE_HEADER,
    CodexTurnSession,
)

CODEX_RESPONSES_LITE_HEADER = "x-openai-internal-codex-responses-lite"


@dataclass(frozen=True)
class ResponsesLiteMapper:
    def to_kwargs(
        self,
        request: CodexLLMRequest,
        *,
        turn_session: CodexTurnSession,
    ) -> dict[str, object]:
        input_items = _to_lite_input(request.messages, turn_session=turn_session)
        tools = [to_codex_tool_payload(tool) for tool in request.tools]
        additional_tools = {
            "type": "additional_tools",
            "role": "developer",
            "tools": _to_lite_tools(tools),
        }
        input_items.insert(0, additional_tools)

        identity = turn_session.identity
        turn_metadata = {
            "installation_id": identity.installation_id,
            "session_id": identity.session_id,
            "thread_id": identity.thread_id,
            "turn_id": identity.turn_id,
            "window_id": identity.window_id,
            "request_kind": "turn",
            "turn_started_at_unix_ms": identity.turn_started_at_unix_ms,
        }
        turn_metadata_json = json.dumps(
            turn_metadata,
            separators=(",", ":"),
            sort_keys=True,
        )
        client_metadata = {
            "x-codex-installation-id": identity.installation_id,
            "session_id": identity.session_id,
            "thread_id": identity.thread_id,
            "x-codex-window-id": identity.window_id,
            "turn_id": identity.turn_id,
            "x-codex-turn-metadata": turn_metadata_json,
        }
        extra_headers = {
            CODEX_RESPONSES_LITE_HEADER: "true",
            "session_id": identity.session_id,
            "thread_id": identity.thread_id,
            "x-client-request-id": identity.thread_id,
            "x-codex-installation-id": identity.installation_id,
            "x-codex-window-id": identity.window_id,
            "x-codex-turn-metadata": turn_metadata_json,
            "x-codex-routing-hint": f"model={request.model.value}",
        }
        if turn_session.turn_state is not None:
            extra_headers[CODEX_TURN_STATE_HEADER] = turn_session.turn_state

        payload: dict[str, object] = {
            "model": request.model.value,
            "input": input_items,
            "prompt_cache_key": request.session_id,
            "extra_headers": extra_headers,
            "extra_body": {"client_metadata": client_metadata},
            "store": False,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": {
                "effort": CODEX_DEFAULT_REASONING_EFFORT.value,
                "context": "all_turns",
            },
            "include": ["reasoning.encrypted_content"],
        }
        if request.response_format is not None:
            response_format = to_codex_response_format_payload(request.response_format)
            payload["text"] = {"format": response_format}
        return payload


def _to_lite_input(
    messages: tuple[LLMMessage, ...],
    *,
    turn_session: CodexTurnSession,
) -> list[dict[str, object]]:
    instructions: list[str] = []
    input_items: list[dict[str, object]] = []
    last_user_index = _last_user_message_index(messages)
    current_assistant_count = sum(
        isinstance(message, LLMAssistantMessage)
        for message in messages[last_user_index + 1 :]
    )
    recorded_batch_count = min(
        current_assistant_count,
        len(turn_session.response_output_batches),
    )
    recorded_batches = turn_session.response_output_batches[-recorded_batch_count:]
    recorded_assistant_start = current_assistant_count - recorded_batch_count
    current_assistant_index = 0
    response_batch_index = 0

    for index, message in enumerate(messages):
        if isinstance(message, LLMSystemMessage):
            instructions.append(message.content)
            continue

        is_current_turn_assistant = (
            index > last_user_index and isinstance(message, LLMAssistantMessage)
        )
        has_recorded_response = current_assistant_index >= recorded_assistant_start
        if is_current_turn_assistant and has_recorded_response:
            response_items = recorded_batches[response_batch_index]
            input_items.extend(copy.deepcopy(response_items))
            current_assistant_index += 1
            response_batch_index += 1
            continue
        if is_current_turn_assistant:
            current_assistant_index += 1

        generic_items = message_to_codex_input_items(message)
        input_items.extend(_to_lite_input_item(item) for item in generic_items)

    instruction_text = "\n\n".join(instructions)
    if instruction_text:
        instruction_item = {
            "type": "message",
            "role": "developer",
            "content": [{"type": "input_text", "text": instruction_text}],
        }
        input_items.insert(0, instruction_item)
    return input_items


def _last_user_message_index(messages: tuple[LLMMessage, ...]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        role = getattr(message, "role", None)
        if getattr(role, "value", None) == "user":
            return index
    return -1


def _to_lite_input_item(item: dict[str, object]) -> dict[str, object]:
    role = item.get("role")
    content = item.get("content")
    if role not in {"user", "assistant", "developer", "system"}:
        return item
    if not isinstance(content, str):
        return item

    content_type = "output_text" if role == "assistant" else "input_text"
    mapped_role = "developer" if role == "system" else role
    return {
        "type": "message",
        "role": mapped_role,
        "content": [{"type": content_type, "text": content}],
    }


def _to_lite_tools(tools: list[dict[str, object]]) -> list[dict[str, object]]:
    namespace_tools: list[dict[str, object]] = []
    for tool in tools:
        namespace_tool = copy.deepcopy(tool)
        namespace_tool["strict"] = bool(namespace_tool.get("strict", False))
        namespace_tools.append(namespace_tool)
    if not namespace_tools:
        return []
    return [
        {
            "type": "namespace",
            "name": "functions",
            "description": "",
            "tools": namespace_tools,
        }
    ]
