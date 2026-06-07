from __future__ import annotations

from dataclasses import dataclass

from stui.port.notify_action_port import NotifyActionAckStatus, NotifyActionPort
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class DoneNotifyActionResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class DoneNotifyActionUseCase:
    notify_action_port: NotifyActionPort

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        action_uid: str,
    ) -> DoneNotifyActionResult:
        ack = self.notify_action_port.done(run_id=run_id, action_uid=action_uid)
        if ack.status == NotifyActionAckStatus.ACCEPTED:
            state.set_notify_action()
            return DoneNotifyActionResult(state=state)
        state.transcript.items.append(
            DispatchErrorItem(message=ack.message or "error: notify action done rejected")
        )
        state.set_status(kind=ViewStatusKind.ERROR, message="Error")
        return DoneNotifyActionResult(state=state)
