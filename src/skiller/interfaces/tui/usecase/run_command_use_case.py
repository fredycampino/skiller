from __future__ import annotations

import asyncio
from dataclasses import dataclass

from skiller.interfaces.tui.port.run_port import (
    CommandAck,
    CommandAckStatus,
    RunObserver,
    RunPort,
)
from skiller.interfaces.tui.usecase.normalize_command_use_case import Command
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    RunAckItem,
    ScreenStatus,
    UserInputItem,
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
        state.transcript_items.append(UserInputItem(text=command.raw_text))
        state.screen_status = ScreenStatus.RUNNING
        state.waiting_prompt = ""
        state.autocompletion = None
        state.prompt_text = ""
        state.prompt_cursor_position = 0
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
                mode=RunMode.FLOW,
                status=RunStatus.RUNNING,
            )
            state.session_key = ack.run_id
            state.transcript_items.append(RunAckItem(skill=raw_args, run_id=ack.run_id))
            state.screen_status = ScreenStatus.RUNNING
            return RunCommandResult(state=state, raw_args=raw_args, ack=ack)

        state.transcript_items.append(
            DispatchErrorItem(message=ack.message or "error: command returned no response")
        )
        state.screen_status = ScreenStatus.ERROR
        return RunCommandResult(state=state, raw_args=raw_args, ack=ack)
