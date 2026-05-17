from __future__ import annotations

from typing import Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.port.event_models import (
    AgentAssistantMessageContextPayload,
    AgentAssistantMessagePayload,
    AgentFinalAssistantMessagePayload,
    AgentLifecyclePayload,
    AgentStopReason,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentToolResultStatus,
    InputReceivedPayload,
    LogEvent,
    LogEventPayload,
    LogEventType,
    OutputPayload,
    RunCreatePayload,
    RunFinishedPayload,
    RunResumePayload,
    RunWaitingPayload,
    StepErrorPayload,
    StepStartedPayload,
    StepSuccessPayload,
)

JsonObject: TypeAlias = dict[str, JsonValue]
ModelT = TypeVar("ModelT", bound=BaseModel)


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    value: JsonObject | None = None
    body_ref: str | None = None
    text_ref: str | None = None


class RunCreateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    source: str


class RunResumeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str


class StepStartedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StepSuccessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: OutputModel
    next_step_id: str | None = Field(default=None, alias="next")


class StepErrorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str


class RunWaitingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: OutputModel


class RunFinishedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    error: str | None = None


class InputReceivedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: JsonObject


class AgentAssistantMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    total_tokens: int


class AgentAssistantMessageContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compaction_enabled: bool
    max_window_ratio: float
    max_window_tokens: int
    total_tokens: int
    model: str


class AgentFinalAssistantMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    context: AgentAssistantMessageContextModel


class AgentToolCallModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_call"]
    turn_id: str
    parent_sequence: int | None = None
    tool_call_id: str
    tool: str
    args: JsonObject


class AgentToolResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_result"]
    turn_id: str
    parent_sequence: int | None = None
    tool_call_id: str
    tool: str
    status: AgentToolResultStatus
    data: JsonObject
    text: str | None = None
    error: str | None = None


class AgentLifecycleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str
    stop_reason: AgentStopReason


class LogEventMapper:
    def map(self, event: CliLogEvent) -> LogEvent:
        return LogEvent(
            sequence=event.sequence,
            event_id=event.event_id,
            run_id=event.run_id,
            event_type=event.event_type,
            step_id=event.step_id,
            step_type=event.step_type,
            agent_sequence=event.agent_sequence,
            created_at=event.created_at,
            payload=self._payload(event),
        )

    def _payload(self, event: CliLogEvent) -> LogEventPayload:
        event_type = event.event_type
        payload = event.payload

        if event_type == LogEventType.RUN_CREATE:
            model = _validate_model(RunCreateModel, payload, "payload")
            return RunCreatePayload(ref=model.ref, source=model.source)

        if event_type == LogEventType.RUN_RESUME:
            model = _validate_model(RunResumeModel, payload, "payload")
            return RunResumePayload(source=model.source)

        if event_type == LogEventType.STEP_STARTED:
            _validate_model(StepStartedModel, payload, "payload")
            return StepStartedPayload()

        if event_type == LogEventType.STEP_SUCCESS:
            model = _validate_model(StepSuccessModel, payload, "payload")
            return StepSuccessPayload(
                output=_to_output_payload(model.output),
                next_step_id=model.next_step_id,
            )

        if event_type == LogEventType.STEP_ERROR:
            model = _validate_model(StepErrorModel, payload, "payload")
            return StepErrorPayload(error=model.error)

        if event_type == LogEventType.RUN_WAITING:
            model = _validate_model(RunWaitingModel, payload, "payload")
            return RunWaitingPayload(output=_to_output_payload(model.output))

        if event_type == LogEventType.RUN_FINISHED:
            model = _validate_model(RunFinishedModel, payload, "payload")
            return RunFinishedPayload(status=model.status, error=model.error)

        if event_type == LogEventType.INPUT_RECEIVED:
            model = _validate_model(InputReceivedModel, payload, "payload")
            return InputReceivedPayload(payload=model.payload)

        if event_type == LogEventType.AGENT_ASSISTANT_MESSAGE:
            model = _validate_model(AgentAssistantMessageModel, payload, "payload")
            return AgentAssistantMessagePayload(
                text=model.text,
                total_tokens=model.total_tokens,
            )

        if event_type == LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE:
            model = _validate_model(AgentFinalAssistantMessageModel, payload, "payload")
            return AgentFinalAssistantMessagePayload(
                text=model.text,
                context=AgentAssistantMessageContextPayload(
                    compaction_enabled=model.context.compaction_enabled,
                    max_window_ratio=model.context.max_window_ratio,
                    max_window_tokens=model.context.max_window_tokens,
                    total_tokens=model.context.total_tokens,
                    model=model.context.model,
                ),
            )

        if event_type == LogEventType.AGENT_TOOL_CALL:
            model = _validate_model(AgentToolCallModel, payload, "payload")
            return AgentToolCallPayload(
                type=model.type,
                turn_id=model.turn_id,
                parent_sequence=model.parent_sequence,
                tool_call_id=model.tool_call_id,
                tool=model.tool,
                args=model.args,
            )

        if event_type == LogEventType.AGENT_TOOL_RESULT:
            model = _validate_model(AgentToolResultModel, payload, "payload")
            return AgentToolResultPayload(
                type=model.type,
                turn_id=model.turn_id,
                parent_sequence=model.parent_sequence,
                tool_call_id=model.tool_call_id,
                tool=model.tool,
                status=model.status,
                data=model.data,
                text=model.text,
                error=model.error,
            )

        if event_type in {
            LogEventType.AGENT_INTERRUPTED,
            LogEventType.AGENT_MAX_TURNS_EXHAUSTED,
        }:
            model = _validate_model(AgentLifecycleModel, payload, "payload")
            return AgentLifecyclePayload(
                turn_id=model.turn_id,
                stop_reason=model.stop_reason,
            )

        raise RuntimeError(f"unsupported log event type: {event_type}")


def _to_output_payload(model: OutputModel) -> OutputPayload:
    return OutputPayload(
        text=model.text,
        value=model.value,
        body_ref=model.body_ref,
        text_ref=model.text_ref,
    )


def _validate_model(
    model_type: type[ModelT],
    value: object,
    label: str,
) -> ModelT:
    try:
        return model_type.model_validate(value)
    except ValidationError as exc:
        raise RuntimeError(f"logs command returned invalid {label}: {exc}") from exc
