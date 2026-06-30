from __future__ import annotations

from dataclasses import dataclass

from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.run_port import RunPort, RunRuntimeStatus, RunRuntimeStatusKind
from stui.port.session_store_port import SessionStorePort
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    PromptMode,
    RunResumeItem,
    ViewStatusKind,
)
from stui.viewmodel.port_to_viewmodel import to_run_status

_RESUMABLE_STATUSES = {
    RunRuntimeStatusKind.RUNNING,
    RunRuntimeStatusKind.WAITING,
}


@dataclass(frozen=True)
class ResumeConsoleResult:
    state: ConsoleScreenState
    resumed: bool = False


@dataclass(frozen=True)
class ResumeConsoleUseCase:
    run_port: RunPort
    events_port: EventsPort
    session_store_port: SessionStorePort
    context: RunEventContext

    def execute(
        self,
        observer: LogEventsListener,
        *,
        state: ConsoleScreenState,
    ) -> ResumeConsoleResult:
        stored_session = self.session_store_port.read()
        if stored_session is None:
            return ResumeConsoleResult(state=state)

        runtime_status = self.run_port.status(stored_session.run_id)
        if not _can_resume(runtime_status):
            self.session_store_port.clear()
            return ResumeConsoleResult(state=state)

        run_status = to_run_status(runtime_status)
        state.load_session(
            run_id=stored_session.run_id,
            run_name=stored_session.run_name,
        )
        state.set_transcript(
            mode=state.transcript.mode,
            items=[
                RunResumeItem(
                    run_id=stored_session.run_id,
                    skill=stored_session.run_name,
                )
            ],
        )
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.DEFAULT)
        state.set_status(
            kind=_view_status_kind(run_status),
            message=runtime_status.prompt,
        )
        self.context.activate_run(
            stored_session.run_id,
            run_name=stored_session.run_name,
            status=run_status,
        )
        self.events_port.subscribe(run_id=stored_session.run_id, listener=observer)
        return ResumeConsoleResult(state=state, resumed=True)


def _can_resume(runtime_status: RunRuntimeStatus | None) -> bool:
    if runtime_status is None:
        return False
    return runtime_status.status in _RESUMABLE_STATUSES


def _view_status_kind(run_status: RunStatus) -> ViewStatusKind:
    if run_status == RunStatus.RUNNING:
        return ViewStatusKind.RUNNING
    return ViewStatusKind.WAITING
