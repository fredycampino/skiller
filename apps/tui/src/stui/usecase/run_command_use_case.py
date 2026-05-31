from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.run_port import (
    RunPort,
    RunRuntimeStatusKind,
)
from stui.usecase.normalize_command_use_case import Command
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    RunAckItem,
    UserInputItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class RunCommandResult:
    state: ConsoleScreenState
    raw_args: str


@dataclass(frozen=True)
class RunCommandUseCase:
    """
    Runs `/run` through the runtime.

    Runtime dispatch fails: record a dispatch error only.
    Runtime dispatch succeeds: activate run context and observe the new run.
    Runtime subscription: delegate replacement of the observed run to the port.
    """

    run_port: RunPort
    events_port: EventsPort
    context: RunEventContext

    async def execute(
        self,
        observer: LogEventsListener,
        *,
        state: ConsoleScreenState,
        command: Command,
    ) -> RunCommandResult:
        raw_args = command.args_text
        state.transcript.items.append(UserInputItem(text=command.raw_text))
        state.prompt.text = ""
        state.prompt.cursor_position = 0

        ack = await asyncio.to_thread(self.run_port.run, raw_args)
        if ack.error:
            state.transcript.items.append(
                DispatchErrorItem(message=f"error: {ack.error.message}")
            )
            state.set_status(kind=ViewStatusKind.ERROR, message=ack.error.message)
            self.context.status = RunStatus.FAILED
            return RunCommandResult(state=state, raw_args=raw_args)

        if ack.status != RunRuntimeStatusKind.CREATED:
            state.transcript.items.append(
                DispatchErrorItem(message=f"error: unexpected run status: {ack.status}")
            )
            state.set_status(
                kind=ViewStatusKind.ERROR,
                message=f"Unexpected run status: {ack.status}",
            )
            self.context.status = RunStatus.FAILED
            return RunCommandResult(state=state, raw_args=raw_args)

        self.context.activate_run(
            ack.run_id,
            run_name=raw_args,
            status=RunStatus.RUNNING,
        )
        state.load_session(run_id=ack.run_id, run_name=raw_args)
        state.set_transcript(
            mode=state.transcript.mode,
            items=[RunAckItem(skill=raw_args, run_id=ack.run_id)],
        )
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.DEFAULT)
        state.set_status(kind=ViewStatusKind.RUNNING)
        self.events_port.subscribe(run_id=ack.run_id, listener=observer)
        return RunCommandResult(state=state, raw_args=raw_args)
