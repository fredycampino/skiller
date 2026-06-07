from __future__ import annotations

import pytest

from stui.port.notify_action_port import NotifyActionAck, NotifyActionAckStatus
from stui.usecase.done_notify_action_use_case import DoneNotifyActionUseCase
from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
    ConsoleScreenState,
    DispatchErrorItem,
    NotifyActionState,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_done_notify_action_use_case_calls_port_and_clears_action() -> None:
    state = ConsoleScreenState()
    state.set_notify_action(
        NotifyActionState(
            run_id="run-1",
            message="Authorize",
            action=ActionOpenUrlItem(
                uid="action-open-1",
                type="open_url",
                label="Open",
                url="https://example.com",
            ),
        )
    )
    port = _FakeNotifyActionPort()

    result = DoneNotifyActionUseCase(notify_action_port=port).execute(
        state=state,
        run_id="run-1",
        action_uid="action-open-1",
    )

    assert result.state is state
    assert state.notify_action is None
    assert port.done_calls == [("run-1", "action-open-1")]


def test_done_notify_action_use_case_reports_port_error() -> None:
    state = ConsoleScreenState()
    port = _FakeNotifyActionPort(
        done_ack=NotifyActionAck(
            status=NotifyActionAckStatus.ERROR,
            run_id="run-1",
            action_uid="action-open-1",
            message="error: action failed",
        )
    )

    result = DoneNotifyActionUseCase(notify_action_port=port).execute(
        state=state,
        run_id="run-1",
        action_uid="action-open-1",
    )

    assert result.state is state
    assert isinstance(state.transcript.items[-1], DispatchErrorItem)
    assert state.transcript.items[-1].message == "error: action failed"
    assert state.view_status.kind == ViewStatusKind.ERROR


class _FakeNotifyActionPort:
    def __init__(self, *, done_ack: NotifyActionAck | None = None) -> None:
        self.done_ack = done_ack or NotifyActionAck(
            status=NotifyActionAckStatus.ACCEPTED,
            run_id="run-1",
            action_uid="action-open-1",
        )
        self.done_calls: list[tuple[str, str]] = []

    def open(self, *, run_id: str, action_uid: str, url: str) -> NotifyActionAck:
        raise AssertionError(f"unexpected open call: {run_id}, {action_uid}, {url}")

    def done(self, *, run_id: str, action_uid: str) -> NotifyActionAck:
        self.done_calls.append((run_id, action_uid))
        return self.done_ack
