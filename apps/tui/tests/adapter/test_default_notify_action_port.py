from __future__ import annotations

from dataclasses import dataclass

import pytest

from stui.adapter.default_notify_action_port import DefaultNotifyActionPort
from stui.port.notify_action_port import NotifyActionAck, NotifyActionAckStatus

pytestmark = pytest.mark.unit


def test_default_notify_action_port_opens_url() -> None:
    opened_urls: list[str] = []
    port = DefaultNotifyActionPort(
        command_adapter=_FakeCommandAdapter(),
        url_opener=_record_opened_url(opened_urls),
    )

    result = port.open(
        run_id="run-1",
        step_id="auth_link",
        url="https://example.com/auth",
    )

    assert result.status == NotifyActionAckStatus.ACCEPTED
    assert opened_urls == ["https://example.com/auth"]


def test_default_notify_action_port_maps_open_failure() -> None:
    port = DefaultNotifyActionPort(
        command_adapter=_FakeCommandAdapter(),
        url_opener=lambda _: False,
    )

    result = port.open(
        run_id="run-1",
        step_id="auth_link",
        url="https://example.com/auth",
    )

    assert result.status == NotifyActionAckStatus.ERROR
    assert result.message == "error: could not open url"


def test_default_notify_action_port_delegates_done() -> None:
    command_adapter = _FakeCommandAdapter()
    port = DefaultNotifyActionPort(command_adapter=command_adapter)

    result = port.done(run_id="run-1", step_id="auth_link")

    assert result.status == NotifyActionAckStatus.ACCEPTED
    assert command_adapter.done_calls == [("run-1", "auth_link")]


@dataclass
class _FakeCommandAdapter:
    def __post_init__(self) -> None:
        self.done_calls: list[tuple[str, str]] = []

    def done(self, *, run_id: str, step_id: str) -> NotifyActionAck:
        self.done_calls.append((run_id, step_id))
        return NotifyActionAck(
            status=NotifyActionAckStatus.ACCEPTED,
            run_id=run_id,
            step_id=step_id,
        )


def _record_opened_url(opened_urls: list[str]):
    def open_url(url: str) -> bool:
        opened_urls.append(url)
        return True

    return open_url
