from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.tool.tool_contract import ToolResult


class ToolExecutionStatus(str, Enum):
    INVALID = "invalid"
    EXECUTED = "executed"
    INTERRUPTED = "interrupted"
    REQUEST_EXCEPTION = "request_exception"
    POLICY_EXCEPTION = "policy_exception"

    def is_terminal(self) -> bool:
        return self in {
            ToolExecutionStatus.INTERRUPTED,
            ToolExecutionStatus.REQUEST_EXCEPTION,
            ToolExecutionStatus.POLICY_EXCEPTION,
        }


@dataclass(frozen=True)
class ToolExecutionRequest:
    run_id: str
    step_id: str
    context_id: str
    turn_id: str
    response: LLMResponse
    allowed_tools: list[str]
    max_tool_calls: int
    turn_loop: AgentLoop

    @property
    def agent_id(self) -> str:
        return self.step_id


@dataclass(frozen=True)
class AgentToolCall:
    turn_id: str
    tool_call_id: str
    tool: str
    parent_sequence: int | None
    args: dict[str, Any]


@dataclass(frozen=True)
class AgentToolResult:
    turn_id: str
    tool_call_id: str
    parent_sequence: int | None
    result: ToolResult


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_call_id: str
    tool: str
    status: ToolExecutionStatus
    error_message: str | None = None


@dataclass(frozen=True)
class ToolExecutionResults:
    items: list[ToolExecutionResult]

    def executed_count(self) -> int:
        return sum(
            1 for item in self.items if item.status == ToolExecutionStatus.EXECUTED
        )

    def is_interrupted(self) -> bool:
        return any(item.status == ToolExecutionStatus.INTERRUPTED for item in self.items)

    def has_exception(self) -> bool:
        return any(
            item.status
            in {
                ToolExecutionStatus.REQUEST_EXCEPTION,
                ToolExecutionStatus.POLICY_EXCEPTION,
            }
            for item in self.items
        )

    def exception_message(self) -> str | None:
        for item in self.items:
            if item.status in {
                ToolExecutionStatus.REQUEST_EXCEPTION,
                ToolExecutionStatus.POLICY_EXCEPTION,
            }:
                return item.error_message
        return None
