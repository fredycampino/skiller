from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from typing import Any, TypeAlias

from skiller.domain.agent.agent_context_model import (
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
    agent_context_payload_from_dict,
    agent_context_payload_to_dict,
)


class RuntimeEventType(StrEnum):
    RUN_CREATE = "RUN_CREATE"
    RUN_RESUME = "RUN_RESUME"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCESS = "STEP_SUCCESS"
    STEP_ERROR = "STEP_ERROR"
    RUN_WAITING = "RUN_WAITING"
    RUN_FINISHED = "RUN_FINISHED"
    ACTION_DONE = "ACTION_DONE"
    AGENT_ASSISTANT_MESSAGE = "AGENT_ASSISTANT_MESSAGE"
    AGENT_FINAL_ASSISTANT_MESSAGE = "AGENT_FINAL_ASSISTANT_MESSAGE"
    AGENT_TOOL_CALL = "AGENT_TOOL_CALL"
    AGENT_TOOL_RESULT = "AGENT_TOOL_RESULT"
    AGENT_INTERRUPTED = "AGENT_INTERRUPTED"
    AGENT_MAX_TURNS_EXHAUSTED = "AGENT_MAX_TURNS_EXHAUSTED"
    INPUT_RECEIVED = "INPUT_RECEIVED"


@dataclass(frozen=True)
class RunCreatedPayload:
    ref: str
    source: str


@dataclass(frozen=True)
class RunResumedPayload:
    source: str


@dataclass(frozen=True)
class RunWaitingPayload:
    output: dict[str, Any]


@dataclass(frozen=True)
class RunFinishedPayload:
    status: str
    error: str | None = None


@dataclass(frozen=True)
class StepStartedPayload:
    pass


@dataclass(frozen=True)
class StepSuccessPayload:
    output: dict[str, Any]
    next: str | None = None


@dataclass(frozen=True)
class StepErrorPayload:
    error: str


@dataclass(frozen=True)
class ActionDonePayload:
    action_type: str
    status: str


@dataclass(frozen=True)
class AgentBodyToolMessage:
    total_tokens: int
    text: str


AgentEventBody: TypeAlias = (
    AgentBodyToolMessage
    | AgentToolCallPayload
    | AgentToolResultPayload
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
class InputReceivedPayload:
    payload: dict[str, Any]


RuntimeEventPayload: TypeAlias = (
    RunCreatedPayload
    | RunResumedPayload
    | RunWaitingPayload
    | RunFinishedPayload
    | StepStartedPayload
    | StepSuccessPayload
    | StepErrorPayload
    | ActionDonePayload
    | AgentEventPayload
    | AgentLifecyclePayload
    | InputReceivedPayload
)


@dataclass(frozen=True)
class RuntimeEventDraft:
    run_id: str
    type: RuntimeEventType
    payload: RuntimeEventPayload
    step_id: str | None = None
    step_type: str | None = None
    agent_sequence: int | None = None


@dataclass(frozen=True)
class RuntimeEvent:
    sequence: int
    id: str
    run_id: str
    type: RuntimeEventType
    step_id: str | None
    step_type: str | None
    agent_sequence: int | None
    created_at: str
    payload: RuntimeEventPayload

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "id": self.id,
            "run_id": self.run_id,
            "type": self.type.value if mode == "json" else self.type,
            "created_at": self.created_at,
            "step_id": self.step_id,
            "step_type": self.step_type,
            "agent_sequence": self.agent_sequence,
            "payload": runtime_event_body_to_dict(self.payload),
        }


def runtime_event_payload_to_dict(payload: object) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)

    if isinstance(payload, AgentEventPayload):
        return {
            "step_id": payload.step_id,
            "turn_id": payload.turn_id,
            "agent_sequence": payload.agent_sequence,
            "body": agent_event_body_to_dict(payload.body),
        }

    if is_dataclass(payload):
        return _without_none(asdict(payload))

    return {}


def runtime_event_body_to_dict(payload: RuntimeEventPayload) -> dict[str, Any]:
    if isinstance(payload, AgentEventPayload):
        return agent_event_body_to_dict(payload.body)

    return runtime_event_payload_to_dict(payload)


def agent_event_body_to_dict(
    payload: AgentEventBody,
) -> dict[str, Any]:
    if isinstance(payload, AgentBodyToolMessage):
        return {
            "total_tokens": payload.total_tokens,
            "text": payload.text,
        }
    return agent_context_payload_to_dict(payload)


def runtime_event_step_id(payload: RuntimeEventPayload) -> str | None:
    if isinstance(payload, AgentEventPayload):
        return payload.step_id
    return None


def runtime_event_step_type(payload: RuntimeEventPayload) -> str | None:
    if isinstance(payload, AgentEventPayload):
        return "agent"
    return None


def runtime_event_agent_sequence(payload: RuntimeEventPayload) -> int | None:
    if isinstance(payload, AgentEventPayload):
        return payload.agent_sequence
    return None


def runtime_event_payload_from_dict(
    *,
    event_type: RuntimeEventType,
    value: dict[str, Any],
) -> RuntimeEventPayload:
    if event_type == RuntimeEventType.RUN_CREATE:
        return RunCreatedPayload(
            ref=str(value.get("ref", "")),
            source=str(value.get("source", "")),
        )

    if event_type == RuntimeEventType.RUN_RESUME:
        return RunResumedPayload(source=str(value.get("source", "")))

    if event_type == RuntimeEventType.RUN_WAITING:
        return RunWaitingPayload(
            output=_dict_value(value.get("output")),
        )

    if event_type == RuntimeEventType.RUN_FINISHED:
        error = value.get("error")
        return RunFinishedPayload(
            status=str(value.get("status", "")),
            error=str(error) if error is not None else None,
        )

    if event_type == RuntimeEventType.STEP_STARTED:
        return StepStartedPayload()

    if event_type == RuntimeEventType.STEP_SUCCESS:
        next_step = value.get("next")
        return StepSuccessPayload(
            output=_dict_value(value.get("output")),
            next=str(next_step) if next_step is not None else None,
        )

    if event_type == RuntimeEventType.STEP_ERROR:
        return StepErrorPayload(
            error=str(value.get("error", "")),
        )

    if event_type == RuntimeEventType.ACTION_DONE:
        return ActionDonePayload(
            action_type=str(value.get("action_type", "")),
            status=str(value.get("status", "")),
        )

    if event_type == RuntimeEventType.INPUT_RECEIVED:
        return InputReceivedPayload(
            payload=_dict_value(value.get("payload")),
        )

    if event_type in {
        RuntimeEventType.AGENT_INTERRUPTED,
        RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED,
    }:
        return AgentLifecyclePayload(
            turn_id=str(value.get("turn_id", "")),
            stop_reason=str(value.get("stop_reason", "")),
        )

    return _agent_event_payload_from_dict(event_type=event_type, value=value)


def _agent_event_payload_from_dict(
    *,
    event_type: RuntimeEventType,
    value: dict[str, Any],
) -> AgentEventPayload:
    raw_body = value.get("body")
    if isinstance(raw_body, dict):
        body = raw_body
    else:
        body = dict(value)
        body.pop("step_id", None)
        body.pop("step_type", None)
        body.pop("agent_sequence", None)

    return AgentEventPayload(
        step_id=str(value.get("step_id", "")),
        turn_id=str(value.get("turn_id", "")),
        agent_sequence=_int_value(value.get("agent_sequence")),
        body=_agent_event_body_from_dict(event_type=event_type, value=body),
    )


def _agent_event_body_from_dict(
    *,
    event_type: RuntimeEventType,
    value: dict[str, Any],
) -> AgentEventBody:
    if event_type in {
        RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
        RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
    }:
        return AgentBodyToolMessage(
            total_tokens=_int_value(value.get("total_tokens")),
            text=str(value.get("text", "")),
        )
    return agent_context_payload_from_dict(
        entry_type=_agent_context_entry_type(event_type),
        value=value,
    )


def _agent_context_entry_type(event_type: RuntimeEventType) -> AgentContextEntryType:
    if event_type == RuntimeEventType.AGENT_TOOL_CALL:
        return AgentContextEntryType.TOOL_CALL
    return AgentContextEntryType.TOOL_RESULT


def _dict_value(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


def _without_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
