from dataclasses import dataclass
from enum import Enum

from skiller.application.ports.llm.llm_port import LLMResponse


@dataclass
class AgentTurnLoop:
    max_turns: int
    turn_count: int = 0

    def has_next(self) -> bool:
        return self.turn_count < self.max_turns

    def advance(self) -> None:
        self.turn_count += 1


class ToolTurnStatus(str, Enum):
    INVALID = "invalid"
    EXECUTED = "executed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class ToolTurnRequest:
    run_id: str
    step_id: str
    context_id: str
    turn_id: str
    response: LLMResponse
    allowed_tools: list[str]
    max_tool_calls: int
    turn_loop: AgentTurnLoop


@dataclass(frozen=True)
class ToolTurnResult:
    tool_call_id: str
    tool: str
    status: ToolTurnStatus


@dataclass(frozen=True)
class ToolTurnResults:
    items: list[ToolTurnResult]

    def executed_count(self) -> int:
        return sum(1 for item in self.items if item.status == ToolTurnStatus.EXECUTED)

    def is_interrupted(self) -> bool:
        return any(item.status == ToolTurnStatus.INTERRUPTED for item in self.items)
