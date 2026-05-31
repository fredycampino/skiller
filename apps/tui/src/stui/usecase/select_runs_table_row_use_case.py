from __future__ import annotations

from dataclasses import dataclass

from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.run_port import RunPort
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    PromptMode,
    ViewStatusKind,
)
from stui.viewmodel.port_to_viewmodel import to_run_status


@dataclass(frozen=True)
class SelectRunsTableRowResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class SelectRunsTableRowUseCase:
    """
    Selects a run from `/runs`.

    Unknown command: close table only.
    Empty run id: close table only.
    Missing runtime status: close table only.
    Non-waiting runtime status: close table only.
    Waiting runtime status: load run, activate context, and observe it.
    """

    run_port: RunPort
    events_port: EventsPort
    context: RunEventContext

    def execute(
        self,
        observer: LogEventsListener,
        *,
        state: ConsoleScreenState,
        prompt_text: str,
        run_id: str,
        run_name: str,
    ) -> SelectRunsTableRowResult:
        state.runs_table.visible = False
        state.runs_table.command = ""

        if prompt_text != "/runs":
            return SelectRunsTableRowResult(state=state)
        if not run_id:
            return SelectRunsTableRowResult(state=state)

        runtime_status = self.run_port.status(run_id)
        if not runtime_status:
            return SelectRunsTableRowResult(state=state)

        run_status = to_run_status(runtime_status)
        allowed_statuses = {
            RunStatus.WAITING_INPUT,
            RunStatus.WAITING_WEBHOOK,
            RunStatus.WAITING_CHANNEL,
        }
        if run_status not in allowed_statuses:
            return SelectRunsTableRowResult(state=state)

        transcript_items = []
        if state.session_key == run_id:
            transcript_items = list(state.transcript.items)

        state.load_session(run_id=run_id, run_name=run_name)
        state.set_transcript(mode=state.transcript.mode, items=transcript_items)
        state.set_autocompletion()
        state.set_prompt(
            waiting_prompt=runtime_status.prompt,
            mode=PromptMode.DEFAULT,
        )
        state.set_status(kind=ViewStatusKind.WAITING)
        self.context.activate_run(
            run_id,
            run_name=run_name,
            status=run_status,
        )
        self.events_port.subscribe(run_id=run_id, listener=observer)
        return SelectRunsTableRowResult(state=state)
