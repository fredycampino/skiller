from __future__ import annotations

import asyncio

import pytest

import stui.usecase.start_console_use_case as start_console_use_case_module
from stui.port.event_models import LogEvent
from stui.port.installation_state_port import InstallationState
from stui.port.run_port import (
    RunDispatch,
    RunDispatchError,
    RunDispatchErrorKind,
    RunRuntimeStatus,
    RunRuntimeStatusKind,
)
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.usecase.start_console_use_case import StartConsoleUseCase
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    RunAckItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


class FakeInstallationStatePort:
    def __init__(self, state: InstallationState) -> None:
        self.state = state

    def read(self) -> InstallationState:
        return self.state


class FakeRunPort:
    def __init__(self, dispatch: RunDispatch) -> None:
        self.dispatch = dispatch
        self.called_with: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        self.called_with.append(raw_args)
        return self.dispatch

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        _ = run_id
        return None


class FakeObserver:
    def notify(self, events: list[LogEvent]) -> None:
        _ = events

    def get_max_page(self) -> int:
        return 100


class FakeEventsPort:
    def __init__(self) -> None:
        self.subscribe_calls: list[str] = []
        self.current_listener: object | None = None

    def subscribe(self, *, run_id: str, listener: object) -> None:
        self.subscribe_calls.append(run_id)
        self.current_listener = listener

    def unsubscribe(self) -> None:
        self.current_listener = None


def test_start_console_use_case_skips_when_runtime_db_exists() -> None:
    async def run() -> None:
        state = ConsoleScreenState(session_key="main")
        run_port = FakeRunPort(_dispatch())
        use_case = _use_case(
            installation_state=InstallationState(
                runtime_db_exists=True,
                agent_config_exists=False,
            ),
            run_port=run_port,
        )

        result = await use_case.execute(FakeObserver(), state=state)

        assert result.state is state
        assert result.started_llmconfig is False
        assert run_port.called_with == []

    asyncio.run(run())


def test_start_console_use_case_skips_when_agent_config_exists() -> None:
    async def run() -> None:
        state = ConsoleScreenState(session_key="main")
        run_port = FakeRunPort(_dispatch())
        use_case = _use_case(
            installation_state=InstallationState(
                runtime_db_exists=False,
                agent_config_exists=True,
            ),
            run_port=run_port,
        )

        result = await use_case.execute(FakeObserver(), state=state)

        assert result.state is state
        assert result.started_llmconfig is False
        assert run_port.called_with == []

    asyncio.run(run())


def test_start_console_use_case_runs_llmconfig_for_first_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        state = ConsoleScreenState(session_key="main")
        events_port = FakeEventsPort()
        observer = FakeObserver()
        context = _run_context()
        run_port = FakeRunPort(_dispatch())
        use_case = _use_case(
            installation_state=InstallationState(
                runtime_db_exists=False,
                agent_config_exists=False,
            ),
            run_port=run_port,
            events_port=events_port,
            context=context,
        )

        result = await use_case.execute(observer, state=state)

        assert result.state is state
        assert result.started_llmconfig is True
        assert run_port.called_with == ["llmconfig"]
        assert events_port.subscribe_calls == ["run-1234"]
        assert events_port.current_listener is observer
        assert context.run_id == "run-1234"
        assert context.skill_name == "llmconfig"
        assert context.mode == RunMode.CHAT
        assert context.status == RunStatus.RUNNING
        assert state.session_key == "run-1234"
        assert state.view_status.kind == ViewStatusKind.RUNNING
        assert len(state.transcript.items) == 1
        assert isinstance(state.transcript.items[0], RunAckItem)
        assert state.transcript.items[0].skill == "llmconfig"
        assert state.transcript.items[0].run_id == "run-1234"

    asyncio.run(run())


def test_start_console_use_case_records_llmconfig_dispatch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_to_thread(monkeypatch)

    async def run() -> None:
        state = ConsoleScreenState(session_key="main")
        context = _run_context()
        use_case = _use_case(
            installation_state=InstallationState(
                runtime_db_exists=False,
                agent_config_exists=False,
            ),
            run_port=FakeRunPort(_dispatch_error()),
            context=context,
        )

        result = await use_case.execute(FakeObserver(), state=state)

        assert result.state is state
        assert result.started_llmconfig is False
        assert context.status == RunStatus.FAILED
        assert state.session_key == "main"
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert state.view_status.message == "agent not found: llmconfig"
        assert isinstance(state.transcript.items[-1], DispatchErrorItem)
        assert state.transcript.items[-1].message == "error: agent not found: llmconfig"

    asyncio.run(run())


def _use_case(
    *,
    installation_state: InstallationState,
    run_port: FakeRunPort,
    events_port: FakeEventsPort | None = None,
    context: RunEventContext | None = None,
) -> StartConsoleUseCase:
    return StartConsoleUseCase(
        installation_state_port=FakeInstallationStatePort(installation_state),
        run_port=run_port,
        events_port=events_port or FakeEventsPort(),
        context=context or _run_context(),
    )


def _patch_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(function, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return function(*args, **kwargs)

    monkeypatch.setattr(start_console_use_case_module.asyncio, "to_thread", fake_to_thread)


def _run_context() -> RunEventContext:
    return RunEventContext(
        run_id="",
        skill_name="",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _dispatch() -> RunDispatch:
    return RunDispatch(
        run_id="run-1234",
        status=RunRuntimeStatusKind.CREATED,
        worker_pid=3,
        error=RunDispatchError(kind=RunDispatchErrorKind.NONE, message=""),
    )


def _dispatch_error() -> RunDispatch:
    return RunDispatch(
        run_id="",
        status=RunRuntimeStatusKind.FAILED,
        worker_pid=0,
        error=RunDispatchError(
            kind=RunDispatchErrorKind.RUN_NOT_FOUND,
            message="agent not found: llmconfig",
        ),
    )
