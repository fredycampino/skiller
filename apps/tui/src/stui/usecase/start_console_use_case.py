from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.event_port import EventsPort, LogEventsListener
from stui.port.installation_state_port import InstallationStatePort
from stui.port.run_port import RunPort, RunRuntimeStatusKind
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    RunAckItem,
    ViewStatusKind,
)

LLM_CONFIG_RUN_ARGS = "llmconfig"


@dataclass(frozen=True)
class StartConsoleResult:
    state: ConsoleScreenState
    started_llmconfig: bool = False


@dataclass(frozen=True)
class StartConsoleUseCase:
    installation_state_port: InstallationStatePort
    run_port: RunPort
    events_port: EventsPort
    context: RunEventContext

    async def execute(
        self,
        observer: LogEventsListener,
        *,
        state: ConsoleScreenState,
    ) -> StartConsoleResult:
        installation_state = self.installation_state_port.read()
        if installation_state.runtime_db_exists:
            return StartConsoleResult(state=state)
        if installation_state.agent_config_exists:
            return StartConsoleResult(state=state)

        ack = await asyncio.to_thread(self.run_port.run, LLM_CONFIG_RUN_ARGS)
        if ack.error:
            state.transcript.items.append(
                DispatchErrorItem(message=f"error: {ack.error.message}")
            )
            state.set_status(kind=ViewStatusKind.ERROR, message=ack.error.message)
            self.context.status = RunStatus.FAILED
            return StartConsoleResult(state=state)

        if ack.status != RunRuntimeStatusKind.CREATED:
            state.transcript.items.append(
                DispatchErrorItem(message=f"error: unexpected run status: {ack.status}")
            )
            state.set_status(
                kind=ViewStatusKind.ERROR,
                message=f"Unexpected run status: {ack.status}",
            )
            self.context.status = RunStatus.FAILED
            return StartConsoleResult(state=state)

        self.context.activate_run(
            ack.run_id,
            run_name=LLM_CONFIG_RUN_ARGS,
            status=RunStatus.RUNNING,
        )
        state.load_session(run_id=ack.run_id, run_name=LLM_CONFIG_RUN_ARGS)
        state.set_transcript(
            mode=state.transcript.mode,
            items=[RunAckItem(skill=LLM_CONFIG_RUN_ARGS, run_id=ack.run_id)],
        )
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.DEFAULT)
        state.set_status(kind=ViewStatusKind.RUNNING)
        self.events_port.subscribe(run_id=ack.run_id, listener=observer)
        return StartConsoleResult(state=state, started_llmconfig=True)
