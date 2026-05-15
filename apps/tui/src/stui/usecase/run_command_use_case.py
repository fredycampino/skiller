from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.run_port import (
    RunPort,
    RunRuntimeStatusKind,
)
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
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


@dataclass(frozen=True)
class RunCommandUseCase:
    """
    Runs `/run` or `/chat` through the runtime.

    Runtime dispatch fails: record a dispatch error only.
    Runtime dispatch succeeds: activate run context and observe the new run.
    Runtime subscription: delegate replacement of the observed run to the port.
    `/chat`: activate the run in chat mode.
    `/run`: activate the run in flow mode.
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
            skill_name=raw_args,
            mode=_resolve_run_mode(command.kind),
            status=RunStatus.RUNNING,
        )
        state.load_session(run_id=ack.run_id)
        state.set_transcript(
            mode=_resolve_transcript_mode(command.kind),
            items=[RunAckItem(skill=raw_args, run_id=ack.run_id)],
        )
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.DEFAULT)
        state.set_status(kind=ViewStatusKind.RUNNING)
        self.events_port.subscribe(run_id=ack.run_id, listener=observer)
        return RunCommandResult(state=state, raw_args=raw_args)


def _resolve_run_mode(command_kind: CommandKind) -> RunMode:
    if command_kind == CommandKind.CHAT:
        return RunMode.CHAT
    return RunMode.FLOW


def _resolve_transcript_mode(command_kind: CommandKind) -> TranscriptMode:
    if command_kind == CommandKind.CHAT:
        return TranscriptMode.CHAT
    return TranscriptMode.FLOW
