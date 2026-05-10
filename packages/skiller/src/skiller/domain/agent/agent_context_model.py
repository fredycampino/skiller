from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.domain.tool.tool_contract import ToolResult


class AgentContextEntryType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


@dataclass(frozen=True)
class AgentContextEntry:
    id: str
    run_id: str
    context_id: str
    sequence: int
    entry_type: AgentContextEntryType
    payload: dict[str, Any]
    source_step_id: str
    idempotency_key: str
    created_at: str


@dataclass(frozen=True)
class AgentContextToolCall:
    id: str
    tool: str
    args: dict[str, object]


@dataclass(frozen=True)
class AgentContextToolResult:
    tool_call_id: str
    result: ToolResult
