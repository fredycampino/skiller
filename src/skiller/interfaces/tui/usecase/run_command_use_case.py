from __future__ import annotations

import asyncio
from dataclasses import dataclass

from skiller.interfaces.tui.port.run_port import (
    CommandAck,
    CommandAckStatus,
    RunObserver,
    RunPort,
)
from skiller.interfaces.tui.usecase.normalize_command_use_case import Command, CommandKind
from skiller.interfaces.tui.usecase.run_event_context import RunEventContext, RunStatus
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    RunAckItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class RunCommandResult:
    state: ConsoleScreenState
    raw_args: str
    ack: CommandAck


@dataclass(frozen=True)
class RunCommandUseCase:
    run_port: RunPort
    context: RunEventContext

    async def execute(
        self,
        observer: RunObserver,
        *,
        state: ConsoleScreenState,
        command: Command,
    ) -> RunCommandResult:
        raw_args = command.args_text
        state.transcript.items.append(UserInputItem(text=command.raw_text))
        if command.kind == CommandKind.CHAT:
            state.transcript.mode = TranscriptMode.CHAT
        state.view_status.kind = ViewStatusKind.RUNNING
        state.view_status.message = ""
        state.prompt.waiting_prompt = ""
        state.prompt.mode = PromptMode.FLOW
        state.autocompletion = None
        state.prompt.text = ""
        state.prompt.cursor_position = 0
        ack = await asyncio.to_thread(self.run_port.run, raw_args)
        if ack.status == CommandAckStatus.ACCEPTED and ack.run_id:
            current_run_id = observer.run_id.strip()
            next_run_id = ack.run_id.strip()
            if current_run_id:
                self.run_port.unsubscribe(observer)
            observer.run_id = next_run_id
            if next_run_id:
                self.run_port.subscribe(observer)
            self.context.activate_run(
                ack.run_id,
                skill_name=raw_args,
                status=RunStatus.RUNNING,
            )
            state.session_key = ack.run_id
            state.transcript.items.append(RunAckItem(skill=raw_args, run_id=ack.run_id))
            state.view_status.kind = ViewStatusKind.RUNNING
            return RunCommandResult(state=state, raw_args=raw_args, ack=ack)

        state.transcript.items.append(
            DispatchErrorItem(message=ack.message or "error: command returned no response")
        )
        state.view_status.kind = ViewStatusKind.ERROR
        state.view_status.message = "Error"
        return RunCommandResult(state=state, raw_args=raw_args, ack=ack)
