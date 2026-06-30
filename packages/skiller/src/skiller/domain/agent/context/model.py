from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypeAlias

from skiller.domain.agent.llm.model import LLMUsage


class AgentContextEntryType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class AgentAssistantMessageType(str, Enum):
    TOOL_CALLS = "tool_calls"
    FINAL = "final"


@dataclass(frozen=True)
class AgentUserMessagePayload:
    text: str
    type: Literal["user_message"] = "user_message"


@dataclass(frozen=True)
class AgentAssistantMessagePayload:
    turn_id: str
    message_type: AgentAssistantMessageType
    text: str
    type: Literal["assistant_message"] = "assistant_message"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "message_type",
            AgentAssistantMessageType(self.message_type),
        )


@dataclass(frozen=True)
class AgentToolCallPayload:
    turn_id: str
    parent_sequence: int | None
    tool_call_id: str
    tool: str
    args: dict[str, object]
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True)
class AgentToolResultPayload:
    turn_id: str
    parent_sequence: int | None
    tool_call_id: str
    tool: str
    status: str
    data: dict[str, Any]
    error: str | None
    type: Literal["tool_result"] = "tool_result"


AgentContextPayload: TypeAlias = (
    AgentUserMessagePayload
    | AgentAssistantMessagePayload
    | AgentToolCallPayload
    | AgentToolResultPayload
)


@dataclass(frozen=True)
class AgentContextEntry:
    id: str
    run_id: str
    context_id: str
    sequence: int
    entry_type: AgentContextEntryType
    payload: AgentContextPayload
    usage: LLMUsage | None
    source_step_id: str
    created_at: str
    message_type: AgentAssistantMessageType | None = None
    window_start_sequence: int | None = None
    delta_tokens: int | None = None
    delta_compact_tokens: int | None = None
    window_base: bool | None = None

    def __post_init__(self) -> None:
        if isinstance(self.payload, dict):
            object.__setattr__(
                self,
                "payload",
                agent_context_payload_from_dict(
                    entry_type=self.entry_type,
                    value=self.payload,
                ),
            )


@dataclass(frozen=True)
class AgentContextUsageMarker:
    sequence: int
    prompt_tokens: int
    delta_tokens: int
    window_start_sequence: int
    window_base: bool


def agent_context_payload_to_dict(payload: AgentContextPayload) -> dict[str, object]:
    if isinstance(payload, AgentUserMessagePayload):
        return {"type": payload.type, "text": payload.text}
    if isinstance(payload, AgentAssistantMessagePayload):
        return {
            "type": payload.type,
            "turn_id": payload.turn_id,
            "message_type": payload.message_type.value,
            "text": payload.text,
        }
    if isinstance(payload, AgentToolCallPayload):
        return {
            "type": payload.type,
            "turn_id": payload.turn_id,
            "parent_sequence": payload.parent_sequence,
            "tool_call_id": payload.tool_call_id,
            "tool": payload.tool,
            "args": _clone(payload.args),
        }
    return {
        "type": payload.type,
        "turn_id": payload.turn_id,
        "parent_sequence": payload.parent_sequence,
        "tool_call_id": payload.tool_call_id,
        "tool": payload.tool,
        "status": payload.status,
        "data": _clone(payload.data),
        "error": payload.error,
    }


def agent_context_payload_from_dict(
    *,
    entry_type: AgentContextEntryType,
    value: dict[str, Any],
) -> AgentContextPayload:
    if entry_type == AgentContextEntryType.USER_MESSAGE:
        return AgentUserMessagePayload(text=str(value.get("text", "")))

    if entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
        return AgentAssistantMessagePayload(
            turn_id=str(value.get("turn_id", "")),
            message_type=AgentAssistantMessageType(str(value.get("message_type", ""))),
            text=str(value.get("text", "")),
        )

    if entry_type == AgentContextEntryType.TOOL_CALL:
        args = value.get("args")
        return AgentToolCallPayload(
            turn_id=str(value.get("turn_id", "")),
            parent_sequence=_optional_int(value.get("parent_sequence")),
            tool_call_id=str(value.get("tool_call_id", "")),
            tool=str(value.get("tool", "")),
            args=_clone(args) if isinstance(args, dict) else {},
        )

    data = value.get("data")
    error = value.get("error")
    return AgentToolResultPayload(
        turn_id=str(value.get("turn_id", "")),
        parent_sequence=_optional_int(value.get("parent_sequence")),
        tool_call_id=str(value.get("tool_call_id", "")),
        tool=str(value.get("tool", "")),
        status=str(value.get("status", "")),
        data=_clone(data) if isinstance(data, dict) else {},
        error=error if isinstance(error, str) else None,
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
