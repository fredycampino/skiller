from __future__ import annotations

import asyncio

import pytest

import skiller.interfaces.tui.viewmodel.console_screen_viewmodel as viewmodel_module
from skiller.interfaces.tui.port.run_port import (
    CommandAck,
    CommandAckStatus,
    ObserverType,
    PollingEvent,
    PollingEventKind,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    InfoItem,
    RunAckItem,
    RunStatusItem,
    RunStepItem,
    ScreenStatus,
    UserInputItem,
)
from skiller.interfaces.tui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel

pytestmark = pytest.mark.unit


class FakeRunPort:
    def __init__(self, ack: CommandAck) -> None:
        self.ack = ack
        self.called_with: list[str] = []
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []

    def run(self, raw_args: str) -> CommandAck:
        self.called_with.append(raw_args)
        return self.ack

    def subscribe(self, observer: object) -> None:
        self.subscribed.append(observer)

    def unsubscribe(self, observer: object) -> None:
        self.unsubscribed.append(observer)


def test_console_screen_state_defaults_to_idle_main_session() -> None:
    state = ConsoleScreenState()

    assert state.session_key == "main"
    assert state.screen_status == ScreenStatus.READY
    assert state.transcript_items == []


def test_console_screen_viewmodel_requests_exit_for_quit() -> None:
    async def run() -> None:
        viewmodel = ConsoleScreenViewModel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
        )

        result = await viewmodel.submit("/quit")

        assert result.should_exit is True
        assert viewmodel.state.transcript_items == []

    asyncio.run(run())


def test_console_screen_viewmodel_dispatches_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id="run-1234",
            message="[run-dispatch] chat:1234\n  ↳ created",
        )
    )
    monkeypatch.setattr(viewmodel_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        viewmodel = ConsoleScreenViewModel(
            session_key="main",
            run_port=run_port,
        )

        result = await viewmodel.submit("/run chat")

        assert result.clear_prompt is True
        assert result.observe_run_id == "run-1234"
        assert run_port.called_with == ["chat"]
        assert isinstance(viewmodel.state.transcript_items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript_items[1], RunAckItem)
        assert viewmodel.state.transcript_items[0].text == "/run chat"
        assert viewmodel.state.transcript_items[1].skill == "chat"
        assert viewmodel.state.transcript_items[1].run_id == "run-1234"
        assert viewmodel.state.screen_status == ScreenStatus.RUNNING

    asyncio.run(run())


def test_console_screen_viewmodel_rejects_plain_text() -> None:
    async def run() -> None:
        viewmodel = ConsoleScreenViewModel(
            session_key="main",
            run_port=FakeRunPort(
                CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"),
            ),
        )

        result = await viewmodel.submit("hola")

        assert result.clear_prompt is True
        assert isinstance(viewmodel.state.transcript_items[0], UserInputItem)
        assert isinstance(viewmodel.state.transcript_items[1], InfoItem)
        assert (
            viewmodel.state.transcript_items[1].text
            == "Use /run <skill> to execute a skill."
        )

    asyncio.run(run())


def test_console_screen_viewmodel_maps_dispatch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    run_port = FakeRunPort(
        CommandAck(
            status=CommandAckStatus.ERROR,
            message="error: skill not found",
        )
    )
    monkeypatch.setattr(viewmodel_module.asyncio, "to_thread", fake_to_thread)

    async def run() -> None:
        viewmodel = ConsoleScreenViewModel(
            session_key="main",
            run_port=run_port,
        )

        await viewmodel.submit("/run missing_skill")

        assert isinstance(viewmodel.state.transcript_items[1], DispatchErrorItem)
        assert viewmodel.state.transcript_items[1].message == "error: skill not found"
        assert viewmodel.state.screen_status == ScreenStatus.ERROR

    asyncio.run(run())


def test_console_screen_viewmodel_subscribes_and_applies_polling_events() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = ConsoleScreenViewModel(
        session_key="main",
        run_port=run_port,
    )

    viewmodel.start_observing("run-1234")
    viewmodel.notify([
        PollingEvent(
            kind=PollingEventKind.LOG,
            run_id="run-1234",
            event_type="STEP_STARTED",
            step="show_message",
            step_type="notify",
            event_id="evt-1",
        ),
        PollingEvent(
            kind=PollingEventKind.STATUS,
            run_id="run-1234",
            status="RUNNING",
            text="[1234] RUNNING",
        ),
        PollingEvent(
            kind=PollingEventKind.STATUS,
            run_id="run-1234",
            status="SUCCEEDED",
            text="[1234] SUCCEEDED",
        ),
    ])

    assert viewmodel.type == ObserverType.RUN
    assert viewmodel.run_id == "run-1234"
    assert run_port.subscribed == [viewmodel]
    assert viewmodel.state.screen_status == ScreenStatus.READY
    assert isinstance(viewmodel.state.transcript_items[0], RunStepItem)
    assert isinstance(viewmodel.state.transcript_items[1], RunStatusItem)
    assert viewmodel.state.transcript_items[0].step_id == "show_message"
    assert viewmodel.state.transcript_items[0].step_type == "notify"
    assert viewmodel.state.transcript_items[1].status == "succeeded"


def test_console_screen_viewmodel_unsubscribes_previous_run() -> None:
    run_port = FakeRunPort(CommandAck(status=CommandAckStatus.ACCEPTED, message="unused"))
    viewmodel = ConsoleScreenViewModel(
        session_key="main",
        run_port=run_port,
    )

    viewmodel.start_observing("run-1")
    viewmodel.start_observing("run-2")
    viewmodel.stop_observing()

    assert run_port.subscribed == [viewmodel, viewmodel]
    assert run_port.unsubscribed == [viewmodel, viewmodel]
    assert viewmodel.run_id == ""
