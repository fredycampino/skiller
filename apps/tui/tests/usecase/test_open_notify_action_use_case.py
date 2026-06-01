from __future__ import annotations

import pytest

from stui.port.notify_action_port import NotifyActionAck, NotifyActionAckStatus
from stui.usecase.open_notify_action_use_case import OpenNotifyActionUseCase
from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
    ConsoleScreenState,
    DispatchErrorItem,
    NotifyActionState,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_open_notify_action_use_case_calls_port() -> None:
    state = ConsoleScreenState()
    state.set_notify_action(
        NotifyActionState(
            run_id="run-1",
            step_id="auth_link",
            message="Authorize",
            action=ActionOpenUrlItem(
                type="open_url",
                label="Open",
                url="https://example.com/oauth/start",
            ),
        )
    )
    port = _FakeNotifyActionPort()

    result = OpenNotifyActionUseCase(notify_action_port=port).execute(
        state=state,
        run_id="run-1",
        step_id="auth_link",
        url="https://example.com/oauth/start",
    )

    assert result.state is state
    assert port.open_calls == [
        ("run-1", "auth_link", "https://example.com/oauth/start")
    ]
    assert port.done_calls == [("run-1", "auth_link")]
    assert state.notify_action is None


def test_open_notify_action_use_case_reports_port_error() -> None:
    state = ConsoleScreenState()
    port = _FakeNotifyActionPort(
        open_ack=NotifyActionAck(
            status=NotifyActionAckStatus.ERROR,
            run_id="run-1",
            step_id="auth_link",
            message="error: browser failed",
        )
    )

    result = OpenNotifyActionUseCase(notify_action_port=port).execute(
        state=state,
        run_id="run-1",
        step_id="auth_link",
        url="https://example.com/oauth/start",
    )

    assert result.state is state
    assert isinstance(state.transcript.items[-1], DispatchErrorItem)
    assert state.transcript.items[-1].message == "error: browser failed"
    assert state.view_status.kind == ViewStatusKind.ERROR
    assert port.done_calls == []


def test_open_notify_action_use_case_reports_done_error() -> None:
    state = ConsoleScreenState()
    port = _FakeNotifyActionPort(
        done_ack=NotifyActionAck(
            status=NotifyActionAckStatus.ERROR,
            run_id="run-1",
            step_id="auth_link",
            message="error: action done failed",
        )
    )

    result = OpenNotifyActionUseCase(notify_action_port=port).execute(
        state=state,
        run_id="run-1",
        step_id="auth_link",
        url="https://example.com/oauth/start",
    )

    assert result.state is state
    assert port.open_calls == [
        ("run-1", "auth_link", "https://example.com/oauth/start")
    ]
    assert port.done_calls == [("run-1", "auth_link")]
    assert isinstance(state.transcript.items[-1], DispatchErrorItem)
    assert state.transcript.items[-1].message == "error: action done failed"
    assert state.view_status.kind == ViewStatusKind.ERROR


class _FakeNotifyActionPort:
    def __init__(
        self,
        *,
        open_ack: NotifyActionAck | None = None,
        done_ack: NotifyActionAck | None = None,
    ) -> None:
        self.open_ack = open_ack or NotifyActionAck(
            status=NotifyActionAckStatus.ACCEPTED,
            run_id="run-1",
            step_id="auth_link",
        )
        self.done_ack = done_ack or NotifyActionAck(
            status=NotifyActionAckStatus.ACCEPTED,
            run_id="run-1",
            step_id="auth_link",
        )
        self.open_calls: list[tuple[str, str, str]] = []
        self.done_calls: list[tuple[str, str]] = []

    def open(self, *, run_id: str, step_id: str, url: str) -> NotifyActionAck:
        self.open_calls.append((run_id, step_id, url))
        return self.open_ack

    def done(self, *, run_id: str, step_id: str) -> NotifyActionAck:
        self.done_calls.append((run_id, step_id))
        return self.done_ack
