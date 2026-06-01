from __future__ import annotations

from typing import Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.port.event_models import (
    ActionBaseValue,
    ActionDonePayload,
    ActionOpenUrlValue,
    ActionRunValue,
    AgentAssistantMessagePayload,
    AgentFinalAssistantMessagePayload,
    AgentLifecyclePayload,
    AgentOutputValue,
    AgentStopReason,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentToolResultStatus,
    AssignOutputValue,
    InputReceivedPayload,
    LogEvent,
    LogEventPayload,
    LogEventType,
    McpOutputValue,
    NotifyActionStatus,
    NotifyActionValue,
    NotifyOutputFormat,
    NotifyOutputValue,
    OutputPayload,
    OutputValue,
    RouteOutputValue,
    RunCreatePayload,
    RunFinishedPayload,
    RunResumePayload,
    RunSnapshotFailedPayload,
    RunSnapshotUpdatedPayload,
    RunWaitingPayload,
    SendOutputValue,
    ShellOutputValue,
    StepErrorPayload,
    StepStartedPayload,
    StepSuccessPayload,
    WaitChannelOutputValue,
    WaitInputOutputValue,
    WaitWebhookOutputValue,
)

JsonObject: TypeAlias = dict[str, JsonValue]
ModelT = TypeVar("ModelT", bound=BaseModel)


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    value: JsonObject | None = None
    body_ref: str | None = None
    text_ref: str | None = None


class NotifyOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = ""
    format: NotifyOutputFormat = NotifyOutputFormat.SIMPLE


class ActionValueModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    label: str


class ActionOpenUrlValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["open_url"]
    label: str
    message: str | None = None
    url: str
    auto: bool = False


class ActionRunValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["run"]
    label: str
    arg: str
    params: str | None = None
    auto: bool = False


class NotifyActionValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = ""
    format: NotifyOutputFormat = NotifyOutputFormat.SIMPLE
    action: JsonObject


class RunCreateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    source: str


class RunResumeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str


class RunSnapshotUpdatedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    ref: str


class RunSnapshotFailedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    ref: str
    error: str


class StepStartedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StepSuccessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: OutputModel
    next_step_id: str | None = Field(default=None, alias="next")


class RunWaitingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: OutputModel


class StepErrorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str


class AgentOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: JsonObject | None = None


class AssignOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned: JsonValue = None


class SendOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = ""
    key: str = ""
    message: str = ""
    message_id: str | None = None


class ShellOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""


class RouteOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_step_id: str = ""


class WaitInputOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = ""
    payload: JsonObject | None = None


class WaitWebhookOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook: str = ""
    key: str = ""
    payload: JsonObject | None = None


class WaitChannelOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = ""
    key: str = ""
    payload: JsonObject | None = None


class McpOutputValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: JsonObject | None = None


class RunFinishedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    error: str | None = None
    action: JsonObject | None = None


class InputReceivedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: JsonObject


class ActionDoneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    status: NotifyActionStatus


class AgentAssistantMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    total_tokens: int


class AgentFinalAssistantMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    total_tokens: int


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

        if event_type == LogEventType.RUN_SNAPSHOT_UPDATED:
            model = _validate_model(RunSnapshotUpdatedModel, payload, "payload")
            return RunSnapshotUpdatedPayload(source=model.source, ref=model.ref)

        if event_type == LogEventType.RUN_SNAPSHOT_FAILED:
            model = _validate_model(RunSnapshotFailedModel, payload, "payload")
            return RunSnapshotFailedPayload(
                source=model.source,
                ref=model.ref,
                error=model.error,
            )

        if event_type == LogEventType.STEP_STARTED:
            _validate_model(StepStartedModel, payload, "payload")
            return StepStartedPayload()

        if event_type == LogEventType.STEP_SUCCESS:
            model = _validate_model(StepSuccessModel, payload, "payload")
            return StepSuccessPayload(
                output=_to_output_payload(event.step_type, model.output),
                next_step_id=model.next_step_id,
            )

        if event_type == LogEventType.STEP_ERROR:
            model = _validate_model(StepErrorModel, payload, "payload")
            return StepErrorPayload(error=model.error)

        if event_type == LogEventType.RUN_WAITING:
            model = _validate_model(RunWaitingModel, payload, "payload")
            return RunWaitingPayload(
                output=_to_output_payload(event.step_type, model.output)
            )

        if event_type == LogEventType.RUN_FINISHED:
            model = _validate_model(RunFinishedModel, payload, "payload")
            action = (
                _to_action_value(model.action, "payload.action")
                if model.action is not None
                else None
            )
            return RunFinishedPayload(
                status=model.status,
                error=model.error,
                action=action,
            )

        if event_type == LogEventType.ACTION_DONE:
            model = _validate_model(ActionDoneModel, payload, "payload")
            return ActionDonePayload(
                type=model.type,
                status=model.status,
            )

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
                total_tokens=model.total_tokens,
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


def _to_output_payload(step_type: str | None, model: OutputModel) -> OutputPayload:
    return OutputPayload(
        text=model.text,
        value=_to_output_value(step_type, model.value),
        body_ref=model.body_ref,
        text_ref=model.text_ref,
    )


def _to_output_value(step_type: str | None, value: JsonObject | None) -> OutputValue:
    output_value = value or {}
    normalized_step_type = (step_type or "").strip().lower()

    if normalized_step_type == "agent":
        model = _validate_model(AgentOutputValueModel, output_value, "output.value")
        return AgentOutputValue(data=model.data)

    if normalized_step_type == "assign":
        model = _validate_model(AssignOutputValueModel, output_value, "output.value")
        return AssignOutputValue(assigned=model.assigned)

    if normalized_step_type == "send":
        model = _validate_model(SendOutputValueModel, output_value, "output.value")
        return SendOutputValue(
            channel=model.channel,
            key=model.key,
            message=model.message,
            message_id=model.message_id,
        )

    if normalized_step_type == "notify":
        if output_value.get("action") is not None:
            model = _validate_model(NotifyActionValueModel, output_value, "output.value")
            return NotifyActionValue(
                message=model.message,
                format=model.format,
                action=_to_action_value(model.action, "output.value.action"),
            )
        model = _validate_model(
            NotifyOutputValueModel,
            _notify_output_payload(output_value),
            "output.value",
        )
        return NotifyOutputValue(
            message=model.message,
            format=model.format,
        )

    if normalized_step_type == "shell":
        model = _validate_model(ShellOutputValueModel, output_value, "output.value")
        return ShellOutputValue(
            ok=model.ok,
            exit_code=model.exit_code,
            stdout=model.stdout,
            stderr=model.stderr,
        )

    if normalized_step_type in {"switch", "when"}:
        model = _validate_model(RouteOutputValueModel, output_value, "output.value")
        return RouteOutputValue(next_step_id=model.next_step_id)

    if normalized_step_type == "wait_input":
        model = _validate_model(WaitInputOutputValueModel, output_value, "output.value")
        return WaitInputOutputValue(prompt=model.prompt, payload=model.payload)

    if normalized_step_type == "wait_webhook":
        model = _validate_model(
            WaitWebhookOutputValueModel,
            output_value,
            "output.value",
        )
        return WaitWebhookOutputValue(
            webhook=model.webhook,
            key=model.key,
            payload=model.payload,
        )

    if normalized_step_type == "wait_channel":
        model = _validate_model(
            WaitChannelOutputValueModel,
            output_value,
            "output.value",
        )
        return WaitChannelOutputValue(
            channel=model.channel,
            key=model.key,
            payload=model.payload,
        )

    if normalized_step_type == "mcp":
        model = _validate_model(McpOutputValueModel, output_value, "output.value")
        return McpOutputValue(data=model.data)

    raise RuntimeError(f"unsupported output step type: {step_type}")


def _notify_output_payload(value: JsonObject) -> JsonObject:
    payload: JsonObject = {
        "message": value.get("message", ""),
    }
    if "format" in value:
        payload["format"] = value["format"]
    return payload


def _to_action_value(value: JsonObject, label: str) -> ActionBaseValue:
    model = _validate_model(ActionValueModel, value, label)
    if model.type == "open_url":
        open_url = _validate_model(
            ActionOpenUrlValueModel,
            value,
            label,
        )
        return ActionOpenUrlValue(
            type=open_url.type,
            label=open_url.label,
            message=open_url.message,
            url=open_url.url,
            auto=open_url.auto,
        )
    if model.type == "run":
        run = _validate_model(
            ActionRunValueModel,
            value,
            label,
        )
        return ActionRunValue(
            type=run.type,
            label=run.label,
            arg=run.arg,
            params=run.params,
            auto=run.auto,
        )
    return ActionBaseValue(
        type=model.type,
        label=model.label,
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
