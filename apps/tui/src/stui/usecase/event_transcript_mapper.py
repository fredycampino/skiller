from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.port.event_models import (
    ActionDonePayload,
    ActionOpenUrlValue,
    ActionRunValue,
    ActionValue,
    AgentAssistantMessagePayload,
    AgentFinalAssistantMessagePayload,
    AgentOutputValue,
    AgentToolCallPayload,
    AgentToolResultPayload,
    ErrorPayload,
    InputReceivedPayload,
    LogEvent,
    LogEventType,
    NotifyActionValue,
    NotifyOutputValue,
    OutputPayload,
    RouteOutputValue,
    RunFinishedPayload,
    RunSnapshotFailedPayload,
    RunSnapshotUpdatedPayload,
    RunWaitingPayload,
    ShellOutputValue,
    StepErrorPayload,
    StepSuccessPayload,
    WaitInputOutputValue,
    WaitWebhookOutputValue,
)
from stui.viewmodel.console_screen_state import (
    ActionItem,
    ActionOpenUrlItem,
    ActionRunItem,
    AgentAssistantMessageItem,
    AgentFinalAssistantMessageItem,
    AgentStepFinalOutputItem,
    AgentStepStopReason,
    AgentStepUsage,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    DispatchErrorItem,
    NotifyActionDoneItem,
    OutputFormat,
    RunFinishedItem,
    RunSnapshotStatus,
    RunStepItem,
    RunSyncSnapshotItem,
    RunWaitingInputItem,
    RunWaitingWebhookItem,
    StepErrorItem,
    StepNotifyActionItem,
    StepNotifyOutputItem,
    StepOutputItem,
    StepShellOutputItem,
    TranscriptItem,
    UserInputItem,
)


@dataclass(frozen=True)
class EventTranscriptMapper:
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def to_transcript(self, events: list[LogEvent]) -> list[TranscriptItem]:
        items: list[TranscriptItem] = []
        for event in sorted(events, key=lambda event: (event.created_at, event.sequence)):
            item = self._to_transcript_item(event=event)
            if item is not None:
                items.append(item)
        return items

    def _to_transcript_item(
        self,
        *,
        event: LogEvent,
    ) -> TranscriptItem | None:
        if event.event_type in {LogEventType.RUN_CREATE, LogEventType.RUN_RESUME}:
            return None

        if event.event_type == LogEventType.RUN_SNAPSHOT_UPDATED:
            payload = _payload(event, RunSnapshotUpdatedPayload)
            return RunSyncSnapshotItem(
                sequence=event.sequence,
                run_id=event.run_id,
                source=payload.source,
                ref=payload.ref,
                status=RunSnapshotStatus.UPDATED,
            )

        if event.event_type == LogEventType.RUN_SNAPSHOT_FAILED:
            payload = _payload(event, RunSnapshotFailedPayload)
            return RunSyncSnapshotItem(
                sequence=event.sequence,
                run_id=event.run_id,
                source=payload.source,
                ref=payload.ref,
                status=RunSnapshotStatus.FAILED,
                error=payload.error,
            )

        if event.event_type == LogEventType.ACTION_DONE:
            payload = _payload(event, ActionDonePayload)
            return NotifyActionDoneItem(
                sequence=event.sequence,
                run_id=event.run_id,
                action_uid=payload.uid,
                type=payload.type,
                status=payload.status.value,
            )

        if event.event_type == LogEventType.INPUT_RECEIVED:
            payload = _payload(event, InputReceivedPayload)
            text = _json_string(payload.payload.get("text")).strip()
            if not text:
                return None
            return UserInputItem(sequence=event.sequence, text=text)

        if event.event_type == LogEventType.AGENT_ASSISTANT_MESSAGE:
            payload = _payload(event, AgentAssistantMessagePayload)
            if not payload.text.strip():
                return None
            return AgentAssistantMessageItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                message_type="assistant",
                text=payload.text,
            )

        if event.event_type == LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE:
            payload = _payload(event, AgentFinalAssistantMessagePayload)
            if not payload.text.strip():
                return None
            return AgentFinalAssistantMessageItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                text=payload.text,
                total_tokens=payload.total_tokens,
            )

        if event.event_type == LogEventType.AGENT_TOOL_CALL:
            payload = _payload(event, AgentToolCallPayload)
            command = _json_string(payload.args.get("command")).strip()
            if not command:
                return None
            return AgentToolCallItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                tool=payload.tool,
                command=command,
            )

        if event.event_type == LogEventType.AGENT_TOOL_RESULT:
            payload = _payload(event, AgentToolResultPayload)
            preview = _agent_tool_result_preview(payload)
            if not preview:
                return None
            return AgentToolResultItem(
                sequence=event.sequence,
                run_id=event.run_id,
                tool=payload.tool,
                preview=preview,
            )

        if event.event_type in {
            LogEventType.AGENT_INTERRUPTED,
            LogEventType.AGENT_MAX_TURNS_EXHAUSTED,
        }:
            return None

        if (
            event.event_type == LogEventType.STEP_STARTED
            and event.step_type in {"wait_input", "wait_webhook"}
        ):
            return None

        if event.event_type == LogEventType.STEP_STARTED:
            return RunStepItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                step_type=event.step_type or "",
            )

        if (
            event.event_type == LogEventType.STEP_SUCCESS
            and event.step_type == "agent"
            and get_stop_reason(event) == AgentStepStopReason.FINAL
        ):
            payload = _payload(event, StepSuccessPayload)
            value = cast(AgentOutputValue, payload.output.value)
            data = cast(dict[str, object], value.data)
            step_id = event.step_id or ""
            stop_reason = get_stop_reason(event)
            final = cast(str, data["final"])
            usage_data = cast(dict[str, object], data["usage"]) if "usage" in data else None
            usage = (
                AgentStepUsage(
                    prompt_tokens=cast(int, usage_data["prompt_tokens"]),
                    completion_tokens=cast(int, usage_data["completion_tokens"]),
                    total_tokens=cast(int, usage_data["total_tokens"]),
                    provider=cast(str, usage_data["provider"]),
                    model=cast(str, usage_data["model"]),
                )
                if usage_data is not None
                else None
            )
            return AgentStepFinalOutputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=step_id,
                stop_reason=stop_reason,
                final=final,
                usage=usage,
                format=OutputFormat.MARKDOWN,
            )

        if (
            event.event_type == LogEventType.STEP_SUCCESS
            and event.step_type == "agent"
        ):
            payload = _payload(event, StepSuccessPayload)
            value = cast(AgentOutputValue, payload.output.value)
            data = cast(dict[str, object], value.data)
            step_id = event.step_id or ""
            stop_reason = get_stop_reason(event)
            message = _agent_notice_text(
                stop_reason=stop_reason,
                data=data,
                strings=self.strings,
            )
            format = OutputFormat.SIMPLE
            if stop_reason in {
                AgentStepStopReason.CONFIG_INVALID,
                AgentStepStopReason.LLM_REQUEST_FAILED,
            }:
                format = OutputFormat.MARKDOWN
            return AgentSystemNoticeItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=step_id,
                text=message,
                format=format,
            )

        if (
            event.event_type == LogEventType.STEP_SUCCESS
            and event.step_type == "wait_input"
        ):
            return None

        if (
            event.event_type == LogEventType.STEP_SUCCESS
            and event.step_type == "notify"
        ):
            payload = _payload(event, StepSuccessPayload)
            if isinstance(payload.output.value, NotifyActionValue):
                output_value = payload.output.value
                return StepNotifyActionItem(
                    sequence=event.sequence,
                    run_id=event.run_id,
                    step_id=event.step_id,
                    step_type=event.step_type,
                    message=output_value.message,
                    action=_action_item(output_value.action),
                )
            output_value = cast(NotifyOutputValue, payload.output.value)
            return StepNotifyOutputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type=event.step_type,
                message=output_value.message,
                format=OutputFormat(output_value.format.value),
                icon="•",
                muted=False,
            )

        if (
            event.event_type == LogEventType.STEP_SUCCESS
            and event.step_type == "shell"
        ):
            payload = _payload(event, StepSuccessPayload)
            return StepShellOutputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type=event.step_type,
                output=_shell_output_text(payload.output),
                format=OutputFormat.SIMPLE,
                icon="▫",
                muted=False,
            )

        if event.event_type == LogEventType.STEP_SUCCESS:
            payload = _payload(event, StepSuccessPayload)
            step_type = event.step_type
            return StepOutputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type=step_type,
                output=_step_output_text(step_type=step_type, output=payload.output),
                format=_resolve_output_format(step_type),
                icon=_resolve_step_output_icon(step_type),
            )

        if event.event_type == LogEventType.STEP_ERROR:
            payload = _payload(event, StepErrorPayload)
            return StepErrorItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                step_type=event.step_type or "",
                message=payload.error or "step failed",
            )

        if event.event_type == LogEventType.OBSERVER_LOOP_ERROR:
            payload = _payload(event, ErrorPayload)
            return DispatchErrorItem(sequence=event.sequence, message=payload.error)

        if (
            event.event_type == LogEventType.RUN_WAITING
            and event.step_type == "wait_input"
        ):
            payload = _payload(event, RunWaitingPayload)
            return RunWaitingInputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type="wait_input",
                step_id=event.step_id,
                prompt=_waiting_prompt(payload.output),
            )

        if (
            event.event_type == LogEventType.RUN_WAITING
            and event.step_type == "wait_webhook"
        ):
            payload = _payload(event, RunWaitingPayload)
            value = cast(WaitWebhookOutputValue, payload.output.value)
            return RunWaitingWebhookItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type="wait_webhook",
                step_id=event.step_id,
                webhook=value.webhook,
                key=value.key,
                icon="↯",
            )

        if event.event_type == LogEventType.RUN_WAITING:
            return None

        if event.event_type == LogEventType.RUN_FINISHED:
            payload = _payload(event, RunFinishedPayload)
            normalized_status = payload.status.strip().lower()
            if normalized_status == "succeeded":
                return RunFinishedItem(
                    sequence=event.sequence,
                    run_id=event.run_id,
                    status="succeeded",
                    action=(
                        _action_item(payload.action)
                        if payload.action is not None
                        else None
                    ),
                )
            return RunFinishedItem(
                sequence=event.sequence,
                run_id=event.run_id,
                status="error",
                message="failed",
                action=(
                    _action_item(payload.action)
                    if payload.action is not None
                    else None
                ),
            )

        return None


def _payload(event: LogEvent, expected: type) -> object:
    if not isinstance(event.payload, expected):
        raise RuntimeError(f"unexpected payload for {event.event_type}")
    return event.payload


def _action_item(action: ActionValue) -> ActionItem:
    if isinstance(action, ActionOpenUrlValue):
        return ActionOpenUrlItem(
            uid=action.uid,
            type=action.type,
            label=action.label,
            message=action.message,
            url=action.url,
            auto=action.auto,
        )
    if isinstance(action, ActionRunValue):
        return ActionRunItem(
            uid=action.uid,
            type=action.type,
            label=action.label,
            arg=action.arg,
            params=action.params,
            auto=action.auto,
        )
    return ActionItem(
        uid=action.uid,
        type=action.type,
        label=action.label,
    )


def get_stop_reason(event: LogEvent) -> AgentStepStopReason:
    payload = _payload(event, StepSuccessPayload)
    value = cast(AgentOutputValue, payload.output.value)
    data = cast(dict[str, object], value.data)
    return AgentStepStopReason(cast(str, data["stop_reason"]))


def _json_string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _output_text(output: OutputPayload) -> str:
    return output.text


def _step_output_text(*, step_type: str, output: OutputPayload) -> str:
    if step_type in {"switch", "when"}:
        return _route_output_text(output)
    return _output_text(output)


def _shell_output_text(output: OutputPayload) -> str:
    value = cast(ShellOutputValue, output.value)
    stdout = value.stdout
    stderr = value.stderr
    parts = [
        value
        for value in (stdout, stderr)
        if value
    ]
    if parts:
        return "\n".join(parts)
    return output.text


def _route_output_text(output: OutputPayload) -> str:
    value = cast(RouteOutputValue, output.value)
    return f"{value.next_step_id}."


def _waiting_prompt(output: OutputPayload) -> str:
    value = cast(WaitInputOutputValue, output.value)
    return value.prompt.strip()


def _resolve_output_format(step_type: str) -> OutputFormat:
    normalized = step_type.strip().lower()
    if normalized == "agent":
        return OutputFormat.MARKDOWN
    return OutputFormat.SIMPLE


def _resolve_step_output_icon(step_type: str) -> str:
    normalized = step_type.strip().lower()
    icons = {
        "assign": "⇢",
        "mcp": "@",
        "send": ">",
        "switch": "↳",
        "wait_channel": "#",
        "wait_webhook": "~",
        "when": "↳",
    }
    return icons.get(normalized, "•")


def _agent_notice_text(
    *,
    stop_reason: AgentStepStopReason,
    data: dict[str, object],
    strings: TuiStrings,
) -> str:
    if stop_reason == AgentStepStopReason.INTERRUPTED:
        return strings.agent_interrupted_notice
    if stop_reason == AgentStepStopReason.MAX_TURNS_EXHAUSTED:
        return strings.agent_max_turns_exhausted_notice
    if stop_reason == AgentStepStopReason.CONFIG_INVALID:
        message = cast(str, data["message"])
        return strings.agent_config_invalid_notice_template.format(
            title=strings.agent_config_invalid_notice_title,
            message=message,
        )
    if stop_reason == AgentStepStopReason.LLM_REQUEST_FAILED:
        message = cast(str, data["message"])
        return strings.agent_llm_request_failed_notice_template.format(
            title=strings.agent_llm_request_failed_notice_title,
            message=message,
        )
    return "Agent notice"


def _agent_tool_result_preview(payload: AgentToolResultPayload) -> str:
    text = (payload.text or "").strip()
    if text:
        return text

    error = (payload.error or "").strip()
    if error:
        return error

    return payload.status.value
