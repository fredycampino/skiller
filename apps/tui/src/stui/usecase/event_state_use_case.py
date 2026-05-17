from __future__ import annotations

from dataclasses import dataclass, field

from stui.port.event_models import (
    AgentFinalAssistantMessagePayload,
    LogEvent,
    LogEventType,
    OutputPayload,
    RunFinishedPayload,
    RunWaitingPayload,
    StepErrorPayload,
)
from stui.usecase.event_transcript_mapper import EventTranscriptMapper
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    AgentUsageState,
    ConsoleScreenState,
    PromptMode,
    ViewStatusKind,
)


@dataclass(frozen=True)
class EventStateResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class EventStateUseCase:
    context: RunEventContext
    transcript_mapper: EventTranscriptMapper = field(default_factory=EventTranscriptMapper)

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        events: list[LogEvent],
    ) -> EventStateResult:
        if not events:
            return EventStateResult(state=state)

        state.transcript.items = self.transcript_mapper.to_transcript(events)
        state.set_agent_usage(self._agent_usage_state(events=events))
        self._project_event(state=state, event=_most_recent_event(events))
        return EventStateResult(state=state)

    def _agent_usage_state(
        self,
        *,
        events: list[LogEvent],
    ) -> AgentUsageState | None:
        for event in reversed(events):
            if event.event_type != LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE:
                continue
            payload: AgentFinalAssistantMessagePayload = event.payload
            return AgentUsageState(
                model=payload.context.model,
                total_tokens=payload.context.total_tokens,
                max_window_tokens=payload.context.max_window_tokens,
            )
        return None

    def _project_event(
        self,
        *,
        state: ConsoleScreenState,
        event: LogEvent,
    ) -> None:
        if event.event_type in {LogEventType.RUN_CREATE, LogEventType.RUN_RESUME}:
            return

        if event.event_type == LogEventType.INPUT_RECEIVED:
            return

        if event.event_type in {
            LogEventType.AGENT_ASSISTANT_MESSAGE,
            LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
            LogEventType.AGENT_TOOL_CALL,
            LogEventType.AGENT_TOOL_RESULT,
            LogEventType.AGENT_INTERRUPTED,
            LogEventType.AGENT_MAX_TURNS_EXHAUSTED,
            LogEventType.STEP_STARTED,
        }:
            state.set_status(kind=ViewStatusKind.RUNNING)
            self.context.status = RunStatus.RUNNING
            return

        if event.event_type == LogEventType.STEP_SUCCESS:
            return

        if event.event_type == LogEventType.STEP_ERROR:
            payload: StepErrorPayload = event.payload
            state.set_prompt(
                text=state.prompt.text,
                cursor_position=state.prompt.cursor_position,
                mode=PromptMode.DEFAULT,
            )
            self.context.status = RunStatus.FAILED
            state.set_status(kind=ViewStatusKind.ERROR, message=payload.error or "step failed")
            return

        if event.event_type == LogEventType.OBSERVER_LOOP_ERROR:
            state.set_status(kind=ViewStatusKind.ERROR, message="Observer error")
            return

        if event.event_type == LogEventType.RUN_WAITING:
            payload: RunWaitingPayload = event.payload
            waiting_status = _resolve_waiting_status(event)
            self.context.status = waiting_status
            state.set_status(kind=ViewStatusKind.WAITING)
            waiting_prompt = ""
            if waiting_status == RunStatus.WAITING_INPUT:
                waiting_prompt = _waiting_prompt(payload.output)
            state.set_prompt(
                text=state.prompt.text,
                cursor_position=state.prompt.cursor_position,
                waiting_prompt=waiting_prompt,
                mode=PromptMode.DEFAULT,
            )
            return

        if event.event_type == LogEventType.RUN_FINISHED:
            payload: RunFinishedPayload = event.payload
            normalized_status = payload.status.strip().lower()
            state.set_prompt(
                text=state.prompt.text,
                cursor_position=state.prompt.cursor_position,
                mode=PromptMode.DEFAULT,
            )
            if normalized_status == "succeeded":
                state.set_status(kind=ViewStatusKind.HIDDEN)
                self.context.status = RunStatus.SUCCESS
                return
            state.set_status(kind=ViewStatusKind.ERROR, message=normalized_status or "failed")
            self.context.status = RunStatus.FAILED

def _waiting_prompt(output: OutputPayload) -> str:
    if output.value:
        prompt = output.value.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
    return output.text.strip()


def _resolve_waiting_status(event: LogEvent) -> RunStatus:
    normalized = (event.step_type or "").strip().lower()
    if normalized == "wait_input":
        return RunStatus.WAITING_INPUT
    if normalized == "wait_webhook":
        return RunStatus.WAITING_WEBHOOK
    if normalized == "wait_channel":
        return RunStatus.WAITING_CHANNEL
    return RunStatus.WAITING_WEBHOOK


def _most_recent_event(events: list[LogEvent]) -> LogEvent:
    return max(events, key=lambda event: (event.created_at, event.sequence))
