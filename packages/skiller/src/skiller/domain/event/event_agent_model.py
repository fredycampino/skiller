from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from skiller.domain.agent.context.model import AgentContextMetrics
from skiller.domain.agent.llm.model import LLMUsage


@dataclass(frozen=True)
class AgentMessageEventBody:
    total_tokens: int
    text: str
    usage: LLMUsage | None
    context: AgentContextMetrics | None


@dataclass(frozen=True)
class AgentToolCallEventBody:
    turn_id: str
    parent_sequence: int | None
    tool_call_id: str
    tool: str
    args: dict[str, object]
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True)
class AgentToolResultEventBody:
    turn_id: str
    parent_sequence: int | None
    tool_call_id: str
    tool: str
    status: str
    data: dict[str, Any]
    text: str | None
    error: str | None
    type: Literal["tool_result"] = "tool_result"


AgentEventBody: TypeAlias = (
    AgentMessageEventBody
    | AgentToolCallEventBody
    | AgentToolResultEventBody
)


@dataclass(frozen=True)
class AgentEventPayload:
    step_id: str
    turn_id: str
    agent_sequence: int
    body: AgentEventBody


@dataclass(frozen=True)
class AgentLifecyclePayload:
    turn_id: str
    stop_reason: str


@dataclass(frozen=True)
class AgentContextCompactedPayload:
    context_id: str
    compaction_id: int
    system_tokens: int
    estimated_request_tokens: int
    estimated_request_compacted_tokens: int
    target_tokens: int
    window_tokens: int
