from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True)
class AgentOutputValue:
    data: JsonObject | None = None


@dataclass(frozen=True)
class AssignOutputValue:
    assigned: JsonValue = None


@dataclass(frozen=True)
class SendOutputValue:
    channel: str = ""
    key: str = ""
    message: str = ""
    message_id: str | None = None


class NotifyOutputFormat(StrEnum):
    SIMPLE = "simple"
    STRUCTURED = "structured"
    MARKDOWN = "markdown"


class NotifyActionType(StrEnum):
    OPEN_URL = "open_url"


class NotifyActionStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"


@dataclass(frozen=True)
class ActionOpenUrlValue:
    label: str
    url: str
    status: NotifyActionStatus = NotifyActionStatus.PENDING
    auto_open: bool = False


@dataclass(frozen=True)
class NotifyOutputValue:
    message: str
    format: NotifyOutputFormat = NotifyOutputFormat.SIMPLE


@dataclass(frozen=True)
class NotifyActionValue:
    message: str
    action: ActionOpenUrlValue
    format: NotifyOutputFormat = NotifyOutputFormat.SIMPLE
    action_type: NotifyActionType = NotifyActionType.OPEN_URL


@dataclass(frozen=True)
class ShellOutputValue:
    ok: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class RouteOutputValue:
    next_step_id: str = ""


@dataclass(frozen=True)
class WaitInputOutputValue:
    prompt: str = ""
    payload: JsonObject | None = None


@dataclass(frozen=True)
class WaitWebhookOutputValue:
    webhook: str = ""
    key: str = ""
    payload: JsonObject | None = None


@dataclass(frozen=True)
class WaitChannelOutputValue:
    channel: str = ""
    key: str = ""
    payload: JsonObject | None = None


@dataclass(frozen=True)
class McpOutputValue:
    data: JsonObject | None = None


OutputValue: TypeAlias = (
    AgentOutputValue
    | AssignOutputValue
    | SendOutputValue
    | NotifyOutputValue
    | NotifyActionValue
    | ShellOutputValue
    | RouteOutputValue
    | WaitInputOutputValue
    | WaitWebhookOutputValue
    | WaitChannelOutputValue
    | McpOutputValue
)


class LogEventType(StrEnum):
    RUN_CREATE = "RUN_CREATE"
    RUN_RESUME = "RUN_RESUME"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCESS = "STEP_SUCCESS"
    STEP_ERROR = "STEP_ERROR"
    RUN_WAITING = "RUN_WAITING"
    RUN_FINISHED = "RUN_FINISHED"
    ACTION_DONE = "ACTION_DONE"
    INPUT_RECEIVED = "INPUT_RECEIVED"
    AGENT_ASSISTANT_MESSAGE = "AGENT_ASSISTANT_MESSAGE"
    AGENT_FINAL_ASSISTANT_MESSAGE = "AGENT_FINAL_ASSISTANT_MESSAGE"
    AGENT_TOOL_CALL = "AGENT_TOOL_CALL"
    AGENT_TOOL_RESULT = "AGENT_TOOL_RESULT"
    AGENT_INTERRUPTED = "AGENT_INTERRUPTED"
    AGENT_MAX_TURNS_EXHAUSTED = "AGENT_MAX_TURNS_EXHAUSTED"
    OBSERVER_LOOP_ERROR = "OBSERVER_LOOP_ERROR"


@dataclass(frozen=True)
class OutputPayload:
    text: str
    value: OutputValue | None
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


@dataclass(frozen=True)
class ActionDonePayload:
    action_type: NotifyActionType
    status: NotifyActionStatus


@dataclass(frozen=True)
class AgentAssistantMessagePayload:
    text: str
    total_tokens: int


@dataclass(frozen=True)
class AgentFinalAssistantMessagePayload:
    text: str
    total_tokens: int


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
    | ActionDonePayload
    | AgentAssistantMessagePayload
    | AgentFinalAssistantMessagePayload
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
