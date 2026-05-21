from __future__ import annotations

import asyncio

import pytest

import stui.usecase.run_command_use_case as run_command_use_case_module
from stui.port.event_models import LogEvent
from stui.port.run_port import (
    RunDispatch,
    RunDispatchError,
    RunDispatchErrorKind,
    RunRuntimeStatusKind,
)
from stui.usecase.normalize_command_use_case import NormalizeCommandUseCase
from stui.usecase.run_command_use_case import RunCommandUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    RunAckItem,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


class FakeRunPort:
    def __init__(self, dispatch: RunDispatch) -> None:
        self.dispatch = dispatch
        self.called_with: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        self.called_with.append(raw_args)
        return self.dispatch

class FakeObserver:
    def notify(self, events: list[LogEvent]) -> None:
        _ = events

    def get_max_page(self) -> int:
        return 100


class FakeEventsPort:
    def __init__(self, *, current_run_id: str = "", current_listener: object | None = None) -> None:
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []
        self.current_run_id = current_run_id
        self.current_listener = current_listener

    def subscribe(self, *, run_id: str, listener: FakeObserver) -> None:
        if self.current_listener is not None:
            previous_listener = self.current_listener
            self.unsubscribe()
            self.unsubscribed.append(previous_listener)
        self.current_listener = listener
        self.current_run_id = run_id
        self.subscribed.append(listener)

    def unsubscribe(self) -> None:
        self.current_listener = None
        self.current_run_id = ""


def test_run_command_use_case_missing_agent_records_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        port = FakeRunPort(_dispatch_error())
        events_port = FakeEventsPort()
        context = _run_context()
        use_case = RunCommandUseCase(run_port=port, events_port=events_port, context=context)
        state = ConsoleScreenState(session_key="main")
        observer = FakeObserver()

        result = await use_case.execute(
            observer,
            state=state,
            command=NormalizeCommandUseCase().execute(text="/run chat"),
        )

        assert port.called_with == ["chat"]
        assert events_port.unsubscribed == []
        assert events_port.subscribed == []
        assert events_port.current_run_id == ""
        assert result.state is state
        assert result.raw_args == "chat"
        assert context.run_id == ""
        assert context.skill_name == ""
        assert context.mode == RunMode.CHAT
        assert context.status == RunStatus.FAILED
        assert state.session_key == "main"
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert state.view_status.message == "agent not found: chat"
        assert isinstance(state.transcript.items[-2], UserInputItem)
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: agent not found: chat"

    asyncio.run(run())


def test_run_command_use_case_dispatch_success_loads_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        port = FakeRunPort(_dispatch())
        events_port = FakeEventsPort()
        context = _run_context()
        use_case = RunCommandUseCase(run_port=port, events_port=events_port, context=context)
        state = ConsoleScreenState(session_key="main")
        observer = FakeObserver()

        result = await use_case.execute(
            observer,
            state=state,
            command=NormalizeCommandUseCase().execute(text="/run   chat  "),
        )

        assert port.called_with == ["chat"]
        assert events_port.subscribed == [observer]
        assert events_port.unsubscribed == []
        assert events_port.current_run_id == "run-1234"
        assert result.state is state
        assert result.raw_args == "chat"
        assert context.run_id == "run-1234"
        assert context.skill_name == "chat"
        assert context.mode == RunMode.CHAT
        assert context.status == RunStatus.RUNNING
        assert state.session_key == "run-1234"
        assert state.view_status.kind == ViewStatusKind.RUNNING
        assert state.prompt.text == ""
        assert state.prompt.cursor_position == 0
        assert len(state.transcript.items) == 1
        assert isinstance(state.transcript.items[0], RunAckItem)
        assert state.transcript.items[0].skill == "chat"
        assert state.transcript.items[0].run_id == "run-1234"

    asyncio.run(run())


def test_run_command_use_case_unexpected_status_records_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        port = FakeRunPort(_dispatch(status=RunRuntimeStatusKind.RUNNING))
        events_port = FakeEventsPort()
        context = _run_context()
        use_case = RunCommandUseCase(run_port=port, events_port=events_port, context=context)
        state = ConsoleScreenState(session_key="main")
        observer = FakeObserver()
        events_port.current_run_id = "old-run"
        events_port.current_listener = observer

        await use_case.execute(
            observer,
            state=state,
            command=NormalizeCommandUseCase().execute(text="/run chat"),
        )

        assert events_port.unsubscribed == []
        assert events_port.subscribed == []
        assert events_port.current_run_id == "old-run"
        assert context.run_id == ""
        assert context.status == RunStatus.FAILED
        assert state.session_key == "main"
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert state.view_status.message == "Unexpected run status: running"
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: unexpected run status: running"

    asyncio.run(run())


def test_run_command_use_case_unsubscribes_existing_observer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        port = FakeRunPort(_dispatch())
        events_port = FakeEventsPort()
        use_case = RunCommandUseCase(
            run_port=port,
            events_port=events_port,
            context=_run_context()
        )
        observer = FakeObserver()
        events_port.current_run_id = "old-run"
        events_port.current_listener = observer

        await use_case.execute(
            observer,
            state=ConsoleScreenState(session_key="main"),
            command=NormalizeCommandUseCase().execute(text="/run chat"),
        )

        assert events_port.unsubscribed == [observer]
        assert events_port.current_run_id == "run-1234"
        assert events_port.subscribed == [observer]

    asyncio.run(run())


def test_run_command_use_case_keeps_current_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        context = _run_context()
        use_case = RunCommandUseCase(
            run_port=FakeRunPort(_dispatch()),
            events_port=FakeEventsPort(),
            context=context,
        )

        await use_case.execute(
            FakeObserver(),
            state=ConsoleScreenState(session_key="main"),
            command=NormalizeCommandUseCase().execute(text="/run ant"),
        )

        assert context.mode == RunMode.CHAT
        assert context.run_id == "run-1234"
        assert context.skill_name == "ant"

    asyncio.run(run())


def _patch_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(run_command_use_case_module.asyncio, "to_thread", fake_to_thread)


def _run_context() -> RunEventContext:
    return RunEventContext(
        run_id="",
        skill_name="",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _dispatch(
    *,
    status: RunRuntimeStatusKind = RunRuntimeStatusKind.CREATED,
) -> RunDispatch:
    return RunDispatch(
        run_id="run-1234",
        status=status,
        worker_pid=3,
        error=RunDispatchError(
            kind=RunDispatchErrorKind.NONE,
            message="",
        ),
    )


def _dispatch_error() -> RunDispatch:
    return RunDispatch(
        run_id="",
        status=RunRuntimeStatusKind.FAILED,
        worker_pid=0,
        error=RunDispatchError(
            kind=RunDispatchErrorKind.RUN_NOT_FOUND,
            message="agent not found: chat",
        )
    )
