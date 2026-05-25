from __future__ import annotations

from dataclasses import dataclass

from stui.port.notify_action_port import NotifyActionAckStatus, NotifyActionPort
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class OpenNotifyActionResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class OpenNotifyActionUseCase:
    notify_action_port: NotifyActionPort

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        step_id: str,
        url: str,
    ) -> OpenNotifyActionResult:
        ack = self.notify_action_port.open(run_id=run_id, step_id=step_id, url=url)
        if ack.status == NotifyActionAckStatus.ACCEPTED:
            done_ack = self.notify_action_port.done(run_id=run_id, step_id=step_id)
            if done_ack.status == NotifyActionAckStatus.ACCEPTED:
                state.set_notify_action()
                return OpenNotifyActionResult(state=state)
            state.transcript.items.append(
                DispatchErrorItem(
                    message=done_ack.message or "error: notify action done rejected"
                )
            )
            state.set_status(kind=ViewStatusKind.ERROR, message="Error")
            return OpenNotifyActionResult(state=state)
        state.transcript.items.append(
            DispatchErrorItem(message=ack.message or "error: notify action open rejected")
        )
        state.set_status(kind=ViewStatusKind.ERROR, message="Error")
        return OpenNotifyActionResult(state=state)
