from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.run_port import CommandAckStatus, RunObserver, RunPort
from stui.port.waiting_port import WaitingPort
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

        state.view_status.kind = ViewStatusKind.RUNNING
        state.view_status.message = ""
        state.prompt.waiting_prompt = ""
        state.prompt.mode = PromptMode.FLOW
        state.autocompletion = None
        state.prompt.text = ""
        state.prompt.cursor_position = 0

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
                status=RunStatus.RUNNING,
            )
            state.session_key = resolved_run_id
            state.transcript.items.append(
                RunResumeItem(
                    run_id=run_id,
                    skill=self.context.skill_name or run_id,
                )
            )
            state.view_status.kind = ViewStatusKind.RUNNING
            return SubmitWaitingInputResult(state=state)

        state.transcript.items.append(
            DispatchErrorItem(message=ack.message or "error: input rejected")
        )
        state.view_status.kind = ViewStatusKind.ERROR
        state.view_status.message = "Error"
        self.context.status = RunStatus.FAILED
        return SubmitWaitingInputResult(state=state)
