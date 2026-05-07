from __future__ import annotations

import asyncio
from dataclasses import dataclass

from skiller.interfaces.tui.port.run_port import CommandAckStatus, RunObserver, RunPort
from skiller.interfaces.tui.port.waiting_port import WaitingPort
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    RunResumeItem,
    ScreenStatus,
    UserInputItem,
)


@dataclass(frozen=True)
class SubmitWaitingInputResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class SubmitWaitingInputUseCase:
    waiting_port: WaitingPort
    run_port: RunPort
    context: RunEventContext

    async def execute(
        self,
        observer: RunObserver,
        *,
        state: ConsoleScreenState,
        text: str,
    ) -> SubmitWaitingInputResult:
        run_id = self.context.run_id.strip()
        normalized_text = text.strip()
        if not run_id:
            return SubmitWaitingInputResult(state=state)

        state.transcript_items.append(UserInputItem(text=normalized_text))
        state.screen_status = ScreenStatus.RUNNING
        state.waiting_prompt = ""
        state.autocompletion = None
        state.prompt_text = ""
        state.prompt_cursor_position = 0

        ack = await asyncio.to_thread(
            self.waiting_port.send_input,
            run_id=run_id,
            text=normalized_text,
        )
        if ack.status == CommandAckStatus.ACCEPTED:
            resolved_run_id = ack.run_id or run_id
            current_run_id = observer.run_id.strip()
            next_run_id = resolved_run_id.strip()
            if current_run_id:
                self.run_port.unsubscribe(observer)
            observer.run_id = next_run_id
            if next_run_id:
                self.run_port.subscribe(observer)
            self.context.activate_run(
                resolved_run_id,
                skill_name=self.context.skill_name or run_id,
                mode=RunMode.FLOW,
                status=RunStatus.RUNNING,
            )
            state.session_key = resolved_run_id
            state.transcript_items.append(
                RunResumeItem(
                    run_id=run_id,
                    skill=self.context.skill_name or run_id,
                )
            )
            state.screen_status = ScreenStatus.RUNNING
            return SubmitWaitingInputResult(state=state)

        state.transcript_items.append(
            DispatchErrorItem(message=ack.message or "error: input rejected")
        )
        state.screen_status = ScreenStatus.ERROR
        self.context.status = RunStatus.FAILED
        return SubmitWaitingInputResult(state=state)
