from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from skiller.interfaces.tui.port.run_port import (
    CommandAckStatus,
    EventObserver,
    ObserverType,
    PollingEvent,
    PollingEventKind,
    RunPort,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    InfoItem,
    RunAckItem,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    ScreenStatus,
    UserInputItem,
)


@dataclass(frozen=True)
class SubmitResult:
    should_exit: bool = False
    clear_prompt: bool = False
    observe_run_id: str | None = None


@dataclass
class ConsoleScreenViewModel(EventObserver):
    type: Literal[ObserverType.RUN] = ObserverType.RUN
    run_id: str = ""
    _run_port: RunPort = field(init=False)
    state: ConsoleScreenState = field(init=False)
    _on_change: Callable[[], None] | None = field(default=None, init=False, repr=False)

    def __init__(self, *, session_key: str, run_port: RunPort) -> None:
        self._run_port = run_port
        self.state = ConsoleScreenState(session_key=session_key)
        self.run_id = ""
        self._on_change = None

    async def submit(self, text: str) -> SubmitResult:
        normalized = text.strip()
        if not normalized:
            return SubmitResult()

        if normalized.lower() in {"/quit", "quit", "exit"}:
            return SubmitResult(should_exit=True)

        if normalized == "/run" or normalized.startswith("/run "):
            return await self._submit_run(normalized)

        self._append_user_input(normalized)
        self._append_info("Use /run <skill> to execute a skill.")
        self.state.screen_status = ScreenStatus.READY
        return SubmitResult(clear_prompt=True)

    async def _submit_run(self, command_text: str) -> SubmitResult:
        raw_args = command_text[4:].strip()
        self.state.screen_status = ScreenStatus.RUNNING

        ack = await asyncio.to_thread(self._run_port.run, raw_args)

        self._append_user_input(command_text)
        if ack.status == CommandAckStatus.ACCEPTED and ack.run_id:
            self._append_run_ack(skill=raw_args, run_id=ack.run_id)
            self.state.screen_status = ScreenStatus.RUNNING
            return SubmitResult(clear_prompt=True, observe_run_id=ack.run_id)

        self._append_dispatch_error(ack.message or "error: command returned no response")
        self.state.screen_status = ScreenStatus.ERROR
        return SubmitResult(clear_prompt=True)

    def start_observing(self, run_id: str) -> None:
        if self.run_id:
            self._run_port.unsubscribe(self)
        self.run_id = run_id
        self._run_port.subscribe(self)

    def stop_observing(self) -> None:
        if not self.run_id:
            return
        self._run_port.unsubscribe(self)
        self.run_id = ""

    def bind_on_change(self, callback: Callable[[], None]) -> None:
        self._on_change = callback

    def notify(self, events: list[PollingEvent]) -> None:
        for event in events:
            if event.kind == PollingEventKind.LOG:
                self._append_log_event(event)
                continue

            normalized_status = event.status.strip().lower() or "ready"
            if normalized_status == "waiting":
                self.state.screen_status = ScreenStatus.WAITING
                self._append_run_status(run_id=event.run_id, status="waiting")
                continue
            if normalized_status == "succeeded":
                self.state.screen_status = ScreenStatus.READY
                self._append_run_status(run_id=event.run_id, status="succeeded")
                continue
            if normalized_status in {"failed", "cancelled"}:
                self.state.screen_status = ScreenStatus.ERROR
                if not self._has_terminal_error_status(event.run_id):
                    self._append_run_status(
                        run_id=event.run_id,
                        status="error",
                        message=normalized_status,
                    )
                continue
            if normalized_status in {"created", "running"}:
                self.state.screen_status = ScreenStatus.RUNNING
                continue
            self.state.screen_status = ScreenStatus.READY

        if self._on_change is not None:
            self._on_change()

    def _append_user_input(self, text: str) -> None:
        self.state.transcript_items.append(UserInputItem(text=text))

    def _append_info(self, text: str) -> None:
        self.state.transcript_items.append(InfoItem(text=text))

    def _append_dispatch_error(self, message: str) -> None:
        self.state.transcript_items.append(DispatchErrorItem(message=message))

    def _append_run_ack(self, *, skill: str, run_id: str) -> None:
        self.state.transcript_items.append(RunAckItem(skill=skill, run_id=run_id))

    def _append_run_step(self, *, run_id: str, step_id: str, step_type: str) -> None:
        self.state.transcript_items.append(
            RunStepItem(
                run_id=run_id,
                step_id=step_id,
                step_type=step_type,
            )
        )

    def _append_run_output(self, *, run_id: str, step_type: str, output: str) -> None:
        self.state.transcript_items.append(
            RunOutputItem(
                run_id=run_id,
                step_type=step_type,
                output=output,
            )
        )

    def _append_run_status(self, *, run_id: str, status: str, message: str = "") -> None:
        if self._is_duplicate_run_status(run_id=run_id, status=status, message=message):
            return
        self.state.transcript_items.append(
            RunStatusItem(
                run_id=run_id,
                status=status,
                message=message,
            )
        )

    def _append_log_event(self, event: PollingEvent) -> None:
        if event.event_type == "RUN_CREATE":
            return
        if event.event_type == "STEP_STARTED":
            self._append_run_step(
                run_id=event.run_id,
                step_id=event.step,
                step_type=event.step_type,
            )
            return
        if event.event_type == "STEP_SUCCESS":
            self._append_run_output(
                run_id=event.run_id,
                step_type=event.step_type,
                output=event.output or "ok",
            )
            return
        if event.event_type == "STEP_ERROR":
            self._append_run_status(
                run_id=event.run_id,
                status="error",
                message=event.error or event.text or "step failed",
            )
            self.state.screen_status = ScreenStatus.ERROR
            return
        if event.event_type == "RUN_WAITING":
            if event.output or event.text:
                self._append_run_output(
                    run_id=event.run_id,
                    step_type=event.step_type,
                    output=event.output or event.text,
                )
            return
        if event.text:
            self._append_info(event.text)

    def _has_terminal_error_status(self, run_id: str) -> bool:
        for item in reversed(self.state.transcript_items):
            if not isinstance(item, RunStatusItem):
                continue
            if item.run_id != run_id:
                continue
            return item.status == "error"
        return False

    def _is_duplicate_run_status(self, *, run_id: str, status: str, message: str) -> bool:
        if not self.state.transcript_items:
            return False
        last_item = self.state.transcript_items[-1]
        if not isinstance(last_item, RunStatusItem):
            return False
        return (
            last_item.run_id == run_id
            and last_item.status == status
            and last_item.message == message
        )
