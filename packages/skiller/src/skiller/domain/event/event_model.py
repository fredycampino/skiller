from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum, StrEnum
from typing import Any, TypeAlias

from skiller.domain.action.action_model import (
    Action,
    ActionStatus,
    ActionType,
    action_from_dict,
    action_to_public_dict,
)
from skiller.domain.agent.context.model import AgentContextMetrics
from skiller.domain.agent.llm.model import LLMUsage
from skiller.domain.event.event_agent_model import (
    AgentContextCompactedPayload,
    AgentEventBody,
    AgentEventPayload,
    AgentLifecyclePayload,
    AgentMessageEventBody,
    AgentToolCallEventBody,
    AgentToolResultEventBody,
)


class RuntimeEventType(StrEnum):
    RUN_CREATE = "RUN_CREATE"
    RUN_RESUME = "RUN_RESUME"
    RUN_SNAPSHOT_UPDATED = "RUN_SNAPSHOT_UPDATED"
    RUN_SNAPSHOT_FAILED = "RUN_SNAPSHOT_FAILED"
    RUN_MODEL_UPDATED = "RUN_MODEL_UPDATED"
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
    AGENT_CONTEXT_COMPACTED = "AGENT_CONTEXT_COMPACTED"
    INPUT_RECEIVED = "INPUT_RECEIVED"


@dataclass(frozen=True)
class RunCreatedPayload:
    ref: str
    source: str


@dataclass(frozen=True)
class RunResumedPayload:
    source: str


@dataclass(frozen=True)
class RunSnapshotUpdatedPayload:
    source: str
    ref: str


@dataclass(frozen=True)
class RunSnapshotFailedPayload:
    source: str
    ref: str
    error: str


@dataclass(frozen=True)
class RunModelUpdatedPayload:
    provider: str
    model: str


@dataclass(frozen=True)
class RunWaitingPayload:
    output: dict[str, Any]


@dataclass(frozen=True)
class RunFinishedPayload:
    status: str
    error: str | None = None
    action: Action | None = None


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
    uid: str
    type: ActionType
    status: ActionStatus


@dataclass(frozen=True)
class InputReceivedPayload:
    payload: dict[str, Any]


RuntimeEventPayload: TypeAlias = (
    RunCreatedPayload
    | RunResumedPayload
    | RunSnapshotUpdatedPayload
    | RunSnapshotFailedPayload
    | RunModelUpdatedPayload
    | RunWaitingPayload
    | RunFinishedPayload
    | StepStartedPayload
    | StepSuccessPayload
    | StepErrorPayload
    | ActionDonePayload
    | AgentEventPayload
    | AgentLifecyclePayload
    | AgentContextCompactedPayload
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

    if isinstance(payload, RunFinishedPayload):
        result = {"status": payload.status}
        if payload.error is not None:
            result["error"] = payload.error
        if payload.action is not None:
            result["action"] = action_to_public_dict(payload.action)
        return result

    if is_dataclass(payload):
        return _without_none(asdict(payload))

    raise TypeError(f"Unsupported runtime event payload: {type(payload).__name__}")


def runtime_event_body_to_dict(payload: RuntimeEventPayload) -> dict[str, Any]:
    if isinstance(payload, AgentEventPayload):
        return agent_event_body_to_dict(payload.body)

    return runtime_event_payload_to_dict(payload)


def agent_event_body_to_dict(
    payload: AgentEventBody,
) -> dict[str, Any]:
    if isinstance(payload, AgentMessageEventBody):
        result: dict[str, Any] = {
            "total_tokens": payload.total_tokens,
            "text": payload.text,
        }
        if payload.usage is not None:
            result["usage"] = _to_public_value(asdict(payload.usage))
        if payload.context is not None:
            result["context"] = _to_public_value(asdict(payload.context))
        return result
    if isinstance(payload, AgentToolCallEventBody):
        return {
            "type": payload.type,
            "turn_id": payload.turn_id,
            "parent_sequence": payload.parent_sequence,
            "tool_call_id": payload.tool_call_id,
            "tool": payload.tool,
            "args": payload.args,
        }
    if isinstance(payload, AgentToolResultEventBody):
        result: dict[str, Any] = {
            "type": payload.type,
            "turn_id": payload.turn_id,
            "parent_sequence": payload.parent_sequence,
            "tool_call_id": payload.tool_call_id,
            "tool": payload.tool,
            "status": payload.status,
            "data": payload.data,
            "error": payload.error,
        }
        if payload.text is not None:
            result["text"] = payload.text
        return result
    raise TypeError(f"Unsupported agent event body: {type(payload).__name__}")


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

    if event_type == RuntimeEventType.RUN_SNAPSHOT_UPDATED:
        return RunSnapshotUpdatedPayload(
            source=str(value.get("source", "")),
            ref=str(value.get("ref", "")),
        )

    if event_type == RuntimeEventType.RUN_SNAPSHOT_FAILED:
        return RunSnapshotFailedPayload(
            source=str(value.get("source", "")),
            ref=str(value.get("ref", "")),
            error=str(value.get("error", "")),
        )

    if event_type == RuntimeEventType.RUN_MODEL_UPDATED:
        return RunModelUpdatedPayload(
            provider=str(value.get("provider", "")),
            model=str(value.get("model", "")),
        )

    if event_type == RuntimeEventType.RUN_WAITING:
        return RunWaitingPayload(
            output=_dict_value(value.get("output")),
        )

    if event_type == RuntimeEventType.RUN_FINISHED:
        raw_action = value.get("action")
        action = None
        if raw_action is not None:
            action = action_from_dict(_dict_value(raw_action))
        error = value.get("error")
        return RunFinishedPayload(
            status=str(value.get("status", "")),
            error=str(error) if error is not None else None,
            action=action,
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
        raw_uid = value.get("uid")
        if not isinstance(raw_uid, str) or not raw_uid.strip():
            raise ValueError("ACTION_DONE uid must be non-empty string")
        return ActionDonePayload(
            uid=raw_uid.strip(),
            type=ActionType(str(value.get("type", ""))),
            status=ActionStatus(str(value.get("status", ""))),
        )

    if event_type == RuntimeEventType.INPUT_RECEIVED:
        return InputReceivedPayload(
            payload=_dict_value(value.get("payload")),
        )

    if event_type == RuntimeEventType.AGENT_CONTEXT_COMPACTED:
        return AgentContextCompactedPayload(
            context_id=str(value.get("context_id", "")),
            compaction_id=_int_value(value.get("compaction_id")),
            system_tokens=_int_value(value.get("system_tokens")),
            estimated_request_tokens=_int_value(value.get("estimated_request_tokens")),
            estimated_request_compacted_tokens=_int_value(
                value.get("estimated_request_compacted_tokens")
            ),
            target_tokens=_int_value(value.get("target_tokens")),
            window_tokens=_int_value(value.get("window_tokens")),
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
        return AgentMessageEventBody(
            total_tokens=_int_value(value.get("total_tokens")),
            text=str(value.get("text", "")),
            usage=_llm_usage_from_dict(value.get("usage")),
            context=_agent_context_metrics_from_dict(value.get("context")),
        )
    if event_type == RuntimeEventType.AGENT_TOOL_CALL:
        args = value.get("args")
        return AgentToolCallEventBody(
            turn_id=str(value.get("turn_id", "")),
            parent_sequence=_optional_int(value.get("parent_sequence")),
            tool_call_id=str(value.get("tool_call_id", "")),
            tool=str(value.get("tool", "")),
            args=dict(args) if isinstance(args, dict) else {},
        )

    data = value.get("data")
    text = value.get("text")
    error = value.get("error")
    return AgentToolResultEventBody(
        turn_id=str(value.get("turn_id", "")),
        parent_sequence=_optional_int(value.get("parent_sequence")),
        tool_call_id=str(value.get("tool_call_id", "")),
        tool=str(value.get("tool", "")),
        status=str(value.get("status", "")),
        data=dict(data) if isinstance(data, dict) else {},
        text=str(text) if text is not None else None,
        error=str(error) if error is not None else None,
    )


def _dict_value(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _int_value(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _llm_usage_from_dict(value: object) -> LLMUsage | None:
    if not isinstance(value, dict):
        return None

    provider = value.get("provider")
    model = value.get("model")
    return LLMUsage(
        prompt_tokens=_optional_int(value.get("prompt_tokens")),
        estimated_system_tokens=_optional_int(value.get("estimated_system_tokens")),
        output_tokens=_optional_int(value.get("output_tokens")),
        total_tokens=_optional_int(value.get("total_tokens")),
        cache_read_tokens=_optional_int(value.get("cache_read_tokens")),
        cache_write_tokens=_optional_int(value.get("cache_write_tokens")),
        provider=_optional_string(provider),
        model=_optional_string(model),
    )


def _agent_context_metrics_from_dict(value: object) -> AgentContextMetrics | None:
    if not isinstance(value, dict):
        return None

    effective_window_tokens = _optional_int(value.get("effective_window_tokens"))
    max_total_tokens_ratio = value.get("max_total_tokens_ratio")
    if effective_window_tokens is None:
        return None
    if isinstance(max_total_tokens_ratio, bool):
        return None
    if not isinstance(max_total_tokens_ratio, (float, int)):
        return None

    return AgentContextMetrics(
        effective_window_tokens=effective_window_tokens,
        max_total_tokens_ratio=float(max_total_tokens_ratio),
    )


def _to_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_public_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _without_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
