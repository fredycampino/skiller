from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.run_port import RunPort
from stui.port.waiting_port import WaitingInputStatus, WaitingPort
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    RunResumeItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class SubmitWaitingInputResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class SubmitWaitingInputUseCase:
    waiting_port: WaitingPort
    run_port: RunPort
    events_port: EventsPort
    context: RunEventContext

    async def execute(
        self,
        observer: LogEventsListener,
        *,
        state: ConsoleScreenState,
        text: str,
    ) -> SubmitWaitingInputResult:
        run_id = self.context.run_id
        if not run_id:
            return SubmitWaitingInputResult(state=state)

        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.DEFAULT)

        ack = await asyncio.to_thread(
            self.waiting_port.send_input,
            run_id=run_id,
            text=text,
        )

        if ack.status != WaitingInputStatus.ACCEPTED:
            state.transcript.items.append(DispatchErrorItem(message=ack.message))
            state.set_status(kind=ViewStatusKind.ERROR, message="Error")
            self.context.status = RunStatus.FAILED
            return SubmitWaitingInputResult(state=state)

        self.context.activate_run(
            ack.run_id,
            run_name=self.context.run_name,
            status=RunStatus.RUNNING,
        )
        state.load_session(run_id=ack.run_id, run_name=self.context.run_name)
        state.transcript.items.append(
            RunResumeItem(
                run_id=run_id,
                skill=self.context.run_name,
            )
        )
        state.set_status(kind=ViewStatusKind.RUNNING)
        self.events_port.subscribe(run_id=ack.run_id, listener=observer)
        return SubmitWaitingInputResult(state=state)
