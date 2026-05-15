from __future__ import annotations

import json
from dataclasses import dataclass

from stui.port.event_models import (
    AgentAssistantMessagePayload,
    AgentLifecyclePayload,
    AgentStopReason,
    AgentToolCallPayload,
    AgentToolResultPayload,
    ErrorPayload,
    InputReceivedPayload,
    LogEvent,
    LogEventType,
    OutputPayload,
    RunFinishedPayload,
    RunWaitingPayload,
    StepErrorPayload,
    StepSuccessPayload,
)
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    DispatchErrorItem,
    OutputFormat,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    RunWaitingInputItem,
    TranscriptItem,
    UserInputItem,
)


@dataclass(frozen=True)
class EventTranscriptMapper:
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

        if event.event_type == LogEventType.INPUT_RECEIVED:
            payload = _payload(event, InputReceivedPayload)
            text = _json_string(payload.payload.get("text")).strip()
            if not text:
                return None
            return UserInputItem(sequence=event.sequence, text=text)

        if event.event_type == LogEventType.AGENT_ASSISTANT_MESSAGE:
            payload = _payload(event, AgentAssistantMessagePayload)
            if payload.message_type.value == "final":
                return None
            if not payload.text.strip():
                return None
            return AgentAssistantMessageItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                message_type=payload.message_type.value,
                text=payload.text,
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
            preview = (payload.text or "").strip()
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
            payload = _payload(event, AgentLifecyclePayload)
            return AgentSystemNoticeItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                text=_agent_notice_text(payload.stop_reason),
            )

        if event.event_type == LogEventType.STEP_STARTED:
            return RunStepItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_id=event.step_id or "",
                step_type=event.step_type or "",
            )

        if event.event_type == LogEventType.STEP_SUCCESS:
            payload = _payload(event, StepSuccessPayload)
            step_type = event.step_type or ""
            if _should_skip_step_success(step_type=step_type, output=payload.output):
                return None
            if step_type.strip().lower() == "agent":
                return AgentAssistantMessageItem(
                    sequence=event.sequence,
                    run_id=event.run_id,
                    step_id=event.step_id or "",
                    message_type="final",
                    text=_agent_final_text(payload.output),
                    format=OutputFormat.MARKDOWN,
                )
            return RunOutputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type=step_type,
                output=_output_text(payload.output),
                format=_resolve_output_format(step_type),
            )

        if event.event_type == LogEventType.STEP_ERROR:
            payload = _payload(event, StepErrorPayload)
            return RunStatusItem(
                sequence=event.sequence,
                run_id=event.run_id,
                status="error",
                message=payload.error or "step failed",
            )

        if event.event_type == LogEventType.OBSERVER_LOOP_ERROR:
            payload = _payload(event, ErrorPayload)
            return DispatchErrorItem(sequence=event.sequence, message=payload.error)

        if event.event_type == LogEventType.RUN_WAITING:
            payload = _payload(event, RunWaitingPayload)
            if (event.step_type or "").strip().lower() != "wait_input":
                return None
            return RunWaitingInputItem(
                sequence=event.sequence,
                run_id=event.run_id,
                step_type=event.step_type or "",
                step_id=event.step_id or "",
                prompt=_waiting_prompt(payload.output),
            )

        if event.event_type == LogEventType.RUN_FINISHED:
            payload = _payload(event, RunFinishedPayload)
            normalized_status = payload.status.strip().lower()
            if normalized_status == "succeeded":
                return RunStatusItem(
                    sequence=event.sequence,
                    run_id=event.run_id,
                    status="succeeded",
                )
            return RunStatusItem(
                sequence=event.sequence,
                run_id=event.run_id,
                status="error",
                message=payload.error or normalized_status or "failed",
            )

        return None


def _payload(event: LogEvent, expected: type) -> object:
    if not isinstance(event.payload, expected):
        raise RuntimeError(f"unexpected payload for {event.event_type}")
    return event.payload


def _json_string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _output_text(output: OutputPayload) -> str:
    if output.value is None:
        return output.text
    return json.dumps(
        {
            "text": output.text,
            "value": output.value,
            "body_ref": output.body_ref,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _should_skip_step_success(*, step_type: str, output: OutputPayload) -> bool:
    normalized = step_type.strip().lower()
    if normalized == "agent":
        stop_reason = _agent_stop_reason(output)
        return stop_reason in {"interrupted", "max_turns_exhausted"}
    if normalized == "wait_input":
        return output.text.strip().lower() == "input received."
    return False


def _agent_stop_reason(output: OutputPayload) -> str:
    if not output.value:
        return ""
    data = output.value.get("data")
    if not isinstance(data, dict):
        return ""
    stop_reason = data.get("stop_reason")
    if not isinstance(stop_reason, str):
        return ""
    return stop_reason.strip().lower()


def _waiting_prompt(output: OutputPayload) -> str:
    if output.value:
        prompt = output.value.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
    return output.text.strip()


def _agent_final_text(output: OutputPayload) -> str:
    normalized = output.text.strip()
    if output.value:
        data = output.value.get("data")
        if isinstance(data, dict):
            final = data.get("final")
            if isinstance(final, dict):
                text = final.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return normalized


def _resolve_output_format(step_type: str) -> OutputFormat:
    normalized = step_type.strip().lower()
    if normalized == "agent":
        return OutputFormat.MARKDOWN
    if normalized == "shell":
        return OutputFormat.STRUCTURED
    return OutputFormat.SIMPLE


def _agent_notice_text(stop_reason: AgentStopReason) -> str:
    if stop_reason == AgentStopReason.INTERRUPTED:
        return "Interrupted by user"
    if stop_reason == AgentStopReason.MAX_TURNS_EXHAUSTED:
        return "Turn limit reached"
    return "Agent notice"
