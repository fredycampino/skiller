from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias


class StepExecutionStatus(str, Enum):
    NEXT = "NEXT"
    COMPLETED = "COMPLETED"
    WAITING = "WAITING"


@dataclass(frozen=True)
class WaitInputResult:
    prompt: str
    payload: dict[str, Any] | None = None
    input_event_id: str | None = None


@dataclass(frozen=True)
class WaitWebhookResult:
    webhook: str
    key: str
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class SwitchResult:
    next: str


@dataclass(frozen=True)
class WhenResult:
    next: str


@dataclass(frozen=True)
class LlmPromptResult:
    text: str
    json: dict[str, Any] | None = None
    model: str | None = None


@dataclass(frozen=True)
class NotifyResult:
    message: str


@dataclass(frozen=True)
class AssignResult:
    value: Any


@dataclass(frozen=True)
class McpResult:
    ok: bool
    text: str
    error: str | None = None
    data: Any | None = None


StepResultPayload: TypeAlias = (
    WaitInputResult
    | WaitWebhookResult
    | SwitchResult
    | WhenResult
    | LlmPromptResult
    | NotifyResult
    | AssignResult
    | McpResult
)


@dataclass(frozen=True)
class StepExecutionResult:
    status: StepExecutionStatus
    next_step_id: str | None = None
    result: StepResultPayload | None = None
