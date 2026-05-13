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
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    ConsoleScreenState,
    DispatchErrorItem,
    OutputFormat,
    PromptMode,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class LogEventReducerResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class LogEventReducerUseCase:
    context: RunEventContext

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        events: list[LogEvent],
    ) -> LogEventReducerResult:
        for event in events:
            if self.context.remember_event_id(event.event_id):
                continue
            self._activate_current_run(
                run_id=event.run_id,
                status=self.context.status,
            )
            self._append_event(state=state, event=event)

        state.transcript.mode = _resolve_transcript_mode(self.context)
        return LogEventReducerResult(state=state)

    def _append_event(self, *, state: ConsoleScreenState, event: LogEvent) -> None:
        if event.event_type in {LogEventType.RUN_CREATE, LogEventType.RUN_RESUME}:
            return

        if event.event_type == LogEventType.INPUT_RECEIVED:
            payload = _payload(event, InputReceivedPayload)
            text = _json_string(payload.payload.get("text")).strip()
            if text:
                state.transcript.items.append(UserInputItem(text=text))
            return

        if event.event_type == LogEventType.AGENT_ASSISTANT_MESSAGE:
            payload = _payload(event, AgentAssistantMessagePayload)
            self._mark_running(state)
            if payload.message_type.value == "final":
                return
            if payload.text.strip():
                state.transcript.items.append(
                    AgentAssistantMessageItem(
                        run_id=event.run_id,
                        step_id=event.step_id or "",
                        message_type=payload.message_type.value,
                        text=payload.text,
                    )
                )
            return

        if event.event_type == LogEventType.AGENT_TOOL_CALL:
            payload = _payload(event, AgentToolCallPayload)
            self._mark_running(state)
            command = _json_string(payload.args.get("command")).strip()
            if command:
                state.transcript.items.append(
                    AgentToolCallItem(
                        run_id=event.run_id,
                        step_id=event.step_id or "",
                        tool=payload.tool,
                        command=command,
                    )
                )
            return

        if event.event_type == LogEventType.AGENT_TOOL_RESULT:
            payload = _payload(event, AgentToolResultPayload)
            self._mark_running(state)
            preview = (payload.text or "").strip()
            if preview:
                state.transcript.items.append(
                    AgentToolResultItem(
                        run_id=event.run_id,
                        tool=payload.tool,
                        preview=preview,
                    )
                )
            return

        if event.event_type in {
            LogEventType.AGENT_INTERRUPTED,
            LogEventType.AGENT_MAX_TURNS_EXHAUSTED,
        }:
            payload = _payload(event, AgentLifecyclePayload)
            self._mark_running(state)
            state.transcript.items.append(
                AgentSystemNoticeItem(
                    run_id=event.run_id,
                    step_id=event.step_id or "",
                    text=_agent_notice_text(payload.stop_reason),
                )
            )
            return

        if event.event_type == LogEventType.STEP_STARTED:
            self._mark_running(state)
            if self._is_duplicate_wait_step(state=state, event=event):
                return
            state.transcript.items.append(
                RunStepItem(
                    run_id=event.run_id,
                    step_id=event.step_id or "",
                    step_type=event.step_type or "",
                )
            )
            return

        if event.event_type == LogEventType.STEP_SUCCESS:
            payload = _payload(event, StepSuccessPayload)
            step_type = event.step_type or ""
            if _should_skip_step_success(step_type=step_type, output=payload.output):
                return
            state.transcript.items.append(
                RunOutputItem(
                    run_id=event.run_id,
                    step_type=step_type,
                    output=_output_text(payload.output),
                    format=_resolve_output_format(step_type),
                )
            )
            return

        if event.event_type == LogEventType.STEP_ERROR:
            payload = _payload(event, StepErrorPayload)
            state.prompt.waiting_prompt = ""
            state.prompt.mode = PromptMode.DEFAULT
            self.context.status = RunStatus.FAILED
            self._append_run_status(
                state=state,
                run_id=event.run_id,
                status="error",
                message=payload.error or "step failed",
            )
            state.view_status.kind = ViewStatusKind.ERROR
            state.view_status.message = payload.error or "step failed"
            return

        if event.event_type == LogEventType.OBSERVER_LOOP_ERROR:
            payload = _payload(event, ErrorPayload)
            state.transcript.items.append(DispatchErrorItem(message=payload.error))
            state.view_status.kind = ViewStatusKind.ERROR
            state.view_status.message = "Observer error"
            return

        if event.event_type == LogEventType.RUN_WAITING:
            payload = _payload(event, RunWaitingPayload)
            waiting_status = self._resolve_waiting_status(state=state, event=event)
            self._activate_current_run(run_id=event.run_id, status=waiting_status)
            state.view_status.kind = ViewStatusKind.WAITING
            state.view_status.message = ""
            state.prompt.mode = PromptMode.DEFAULT
            if waiting_status == RunStatus.WAITING_INPUT:
                state.prompt.waiting_prompt = _waiting_prompt(payload.output)
                return
            if _output_text(payload.output):
                state.transcript.items.append(
                    RunOutputItem(
                        run_id=event.run_id,
                        step_type=event.step_type or "",
                        output=_output_text(payload.output),
                        format=_resolve_output_format(event.step_type or ""),
                    )
                )
            return

        if event.event_type == LogEventType.RUN_FINISHED:
            payload = _payload(event, RunFinishedPayload)
            normalized_status = payload.status.strip().lower()
            if normalized_status == "succeeded":
                state.view_status.kind = ViewStatusKind.HIDDEN
                state.view_status.message = ""
                state.prompt.waiting_prompt = ""
                state.prompt.mode = PromptMode.DEFAULT
                self.context.status = RunStatus.SUCCESS
                self._append_run_status(state=state, run_id=event.run_id, status="succeeded")
                return
            state.view_status.kind = ViewStatusKind.ERROR
            state.view_status.message = normalized_status or "failed"
            state.prompt.waiting_prompt = ""
            state.prompt.mode = PromptMode.DEFAULT
            self.context.status = RunStatus.FAILED
            self._append_run_status(
                state=state,
                run_id=event.run_id,
                status="error",
                message=payload.error or normalized_status or "failed",
            )

    def _mark_running(self, state: ConsoleScreenState) -> None:
        state.view_status.kind = ViewStatusKind.RUNNING
        state.view_status.message = ""
        self.context.status = RunStatus.RUNNING

    def _activate_current_run(self, *, run_id: str, status: RunStatus) -> None:
        self.context.activate_run(
            run_id,
            skill_name=self.context.skill_name,
            mode=self.context.mode,
            status=status,
        )

    def _append_run_status(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        status: str,
        message: str = "",
    ) -> None:
        if state.transcript.items and isinstance(state.transcript.items[-1], RunStatusItem):
            last = state.transcript.items[-1]
            if last.run_id == run_id and last.status == status and last.message == message:
                return
        state.transcript.items.append(
            RunStatusItem(
                run_id=run_id,
                status=status,
                message=message,
            )
        )

    def _is_duplicate_wait_step(self, *, state: ConsoleScreenState, event: LogEvent) -> bool:
        if (event.step_type or "").strip().lower() != "wait_input":
            return False
        for item in state.transcript.items:
            if not isinstance(item, RunStepItem):
                continue
            if item.run_id != event.run_id:
                continue
            if item.step_id == (event.step_id or "") and item.step_type == (event.step_type or ""):
                return True
        return False

    def _resolve_waiting_status(self, *, state: ConsoleScreenState, event: LogEvent) -> RunStatus:
        waiting_status = _resolve_waiting_status_for_step(event.step_type or "")
        if waiting_status != RunStatus.WAITING_WEBHOOK:
            return waiting_status
        for item in state.transcript.items:
            if not isinstance(item, RunStepItem):
                continue
            if item.run_id != event.run_id:
                continue
            if item.step_id == (event.step_id or "") and item.step_type == "wait_input":
                return RunStatus.WAITING_INPUT
        return waiting_status


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


def _waiting_prompt(output: OutputPayload) -> str:
    if output.value:
        prompt = output.value.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
    return output.text.strip()


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


def _resolve_output_format(step_type: str) -> OutputFormat:
    normalized = step_type.strip().lower()
    if normalized == "agent":
        return OutputFormat.MARKDOWN
    if normalized == "shell":
        return OutputFormat.STRUCTURED
    return OutputFormat.SIMPLE


def _resolve_waiting_status_for_step(step_type: str) -> RunStatus:
    normalized = step_type.strip().lower()
    if normalized == "wait_input":
        return RunStatus.WAITING_INPUT
    if normalized == "wait_webhook":
        return RunStatus.WAITING_WEBHOOK
    if normalized == "wait_channel":
        return RunStatus.WAITING_CHANNEL
    return RunStatus.WAITING_WEBHOOK


def _agent_notice_text(stop_reason: AgentStopReason) -> str:
    if stop_reason == AgentStopReason.INTERRUPTED:
        return "Interrupted by user"
    if stop_reason == AgentStopReason.MAX_TURNS_EXHAUSTED:
        return "Turn limit reached"
    return "Agent notice"


def _resolve_transcript_mode(context: RunEventContext) -> TranscriptMode:
    if context.mode == RunMode.CHAT:
        return TranscriptMode.CHAT
    return TranscriptMode.FLOW
