from __future__ import annotations

from dataclasses import dataclass

import pytest

from apps.tui.tests.support import FakeEventsPort, FakeSessionStorePort
from stui.port.event_models import LogEvent
from stui.port.run_port import (
    RunDispatch,
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)
from stui.port.session_store_port import StoredSession
from stui.usecase.resume_console_use_case import ResumeConsoleUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import ConsoleScreenState, RunResumeItem, ViewStatusKind

pytestmark = pytest.mark.unit


@dataclass
class FakeObserver:
    def notify(self, events: list[LogEvent]) -> None:
        _ = events

    def get_max_page(self) -> int:
        return 100


class FakeRunPort:
    def __init__(self, status: RunRuntimeStatus | None) -> None:
        self.runtime_status = status
        self.status_calls: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        raise AssertionError(f"unexpected run: {raw_args}")

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        self.status_calls.append(run_id)
        return self.runtime_status


def test_resume_console_loads_waiting_session() -> None:
    state = ConsoleScreenState(session_key="main")
    context = _context()
    events_port = FakeEventsPort()
    session_store = FakeSessionStorePort(StoredSession(run_id="run-1", run_name="chat"))
    use_case = ResumeConsoleUseCase(
        run_port=FakeRunPort(
            RunRuntimeStatus(
                run_id="run-1",
                status=RunRuntimeStatusKind.WAITING,
                wait_type=RunRuntimeWaitType.INPUT,
                prompt="Say something",
            )
        ),
        events_port=events_port,
        session_store_port=session_store,
        context=context,
    )

    result = use_case.execute(FakeObserver(), state=state)

    assert result.resumed is True
    assert state.session_key == "run-1"
    assert state.run_name == "chat"
    assert state.view_status.kind == ViewStatusKind.WAITING
    assert state.view_status.message == "Say something"
    assert context.run_id == "run-1"
    assert context.run_name == "chat"
    assert context.status == RunStatus.WAITING_INPUT
    assert events_port.subscribe_calls == ["run-1"]
    assert isinstance(state.transcript.items[0], RunResumeItem)


def test_resume_console_loads_running_session() -> None:
    state = ConsoleScreenState(session_key="main")
    context = _context()
    use_case = ResumeConsoleUseCase(
        run_port=FakeRunPort(RunRuntimeStatus(run_id="run-1", status=RunRuntimeStatusKind.RUNNING)),
        events_port=FakeEventsPort(),
        session_store_port=FakeSessionStorePort(StoredSession(run_id="run-1", run_name="chat")),
        context=context,
    )

    result = use_case.execute(FakeObserver(), state=state)

    assert result.resumed is True
    assert state.view_status.kind == ViewStatusKind.RUNNING
    assert context.status == RunStatus.RUNNING


def test_resume_console_clears_finished_session() -> None:
    state = ConsoleScreenState(session_key="main")
    session_store = FakeSessionStorePort(StoredSession(run_id="run-1", run_name="chat"))
    use_case = ResumeConsoleUseCase(
        run_port=FakeRunPort(
            RunRuntimeStatus(
                run_id="run-1",
                status=RunRuntimeStatusKind.SUCCEEDED,
            )
        ),
        events_port=FakeEventsPort(),
        session_store_port=session_store,
        context=_context(),
    )

    result = use_case.execute(FakeObserver(), state=state)

    assert result.resumed is False
    assert state.session_key == "main"
    assert session_store.clear_calls == 1


def test_resume_console_ignores_missing_session() -> None:
    state = ConsoleScreenState(session_key="main")
    use_case = ResumeConsoleUseCase(
        run_port=FakeRunPort(RunRuntimeStatus(run_id="run-1", status=RunRuntimeStatusKind.RUNNING)),
        events_port=FakeEventsPort(),
        session_store_port=FakeSessionStorePort(),
        context=_context(),
    )

    result = use_case.execute(FakeObserver(), state=state)

    assert result.resumed is False
    assert state.session_key == "main"


def _context() -> RunEventContext:
    return RunEventContext(
        run_id="",
        run_name="",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )
