from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class LogEventType(StrEnum):
    RUN_CREATE = "RUN_CREATE"
    RUN_RESUME = "RUN_RESUME"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCESS = "STEP_SUCCESS"
    STEP_ERROR = "STEP_ERROR"
    RUN_WAITING = "RUN_WAITING"
    RUN_FINISHED = "RUN_FINISHED"
    INPUT_RECEIVED = "INPUT_RECEIVED"
    AGENT_ASSISTANT_MESSAGE = "AGENT_ASSISTANT_MESSAGE"
    AGENT_TOOL_CALL = "AGENT_TOOL_CALL"
    AGENT_TOOL_RESULT = "AGENT_TOOL_RESULT"
    AGENT_INTERRUPTED = "AGENT_INTERRUPTED"
    AGENT_MAX_TURNS_EXHAUSTED = "AGENT_MAX_TURNS_EXHAUSTED"
    OBSERVER_LOOP_ERROR = "OBSERVER_LOOP_ERROR"


@dataclass(frozen=True)
class OutputPayload:
    text: str
    value: dict[str, JsonValue] | None
    body_ref: str | None
    text_ref: str | None = None


@dataclass(frozen=True)
class RunCreatePayload:
    ref: str
    source: str


@dataclass(frozen=True)
class RunResumePayload:
    source: str


@dataclass(frozen=True)
class StepStartedPayload:
    pass


@dataclass(frozen=True)
class StepSuccessPayload:
    output: OutputPayload
    next_step_id: str | None = None


@dataclass(frozen=True)
class StepErrorPayload:
    error: str


@dataclass(frozen=True)
class RunWaitingPayload:
    output: OutputPayload


@dataclass(frozen=True)
class RunFinishedPayload:
    status: str
    error: str | None = None


@dataclass(frozen=True)
class InputReceivedPayload:
    payload: dict[str, JsonValue]


class AgentAssistantMessageType(StrEnum):
    TOOL_CALLS = "tool_calls"
    FINAL = "final"


@dataclass(frozen=True)
class AgentAssistantMessagePayload:
    type: str
    turn_id: str
    message_type: AgentAssistantMessageType
    text: str


@dataclass(frozen=True)
class AgentToolCallPayload:
    type: str
    turn_id: str
    parent_sequence: int | None
    tool_call_id: str
    tool: str
    args: dict[str, JsonValue]


class AgentToolResultStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AgentToolResultPayload:
    type: str
    turn_id: str
    parent_sequence: int | None
    tool_call_id: str
    tool: str
    status: AgentToolResultStatus
    data: dict[str, JsonValue]
    text: str | None
    error: str | None


class AgentStopReason(StrEnum):
    INTERRUPTED = "interrupted"
    MAX_TURNS_EXHAUSTED = "max_turns_exhausted"


@dataclass(frozen=True)
class AgentLifecyclePayload:
    turn_id: str
    stop_reason: AgentStopReason


@dataclass(frozen=True)
class ErrorPayload:
    error: str


LogEventPayload: TypeAlias = (
    RunCreatePayload
    | RunResumePayload
    | StepStartedPayload
    | StepSuccessPayload
    | StepErrorPayload
    | RunWaitingPayload
    | RunFinishedPayload
    | InputReceivedPayload
    | AgentAssistantMessagePayload
    | AgentToolCallPayload
    | AgentToolResultPayload
    | AgentLifecyclePayload
    | ErrorPayload
)


@dataclass(frozen=True)
class LogEvent:
    sequence: int
    event_id: str
    run_id: str
    event_type: LogEventType
    step_id: str | None
    step_type: str | None
    agent_sequence: int | None
    created_at: str
    payload: LogEventPayload
