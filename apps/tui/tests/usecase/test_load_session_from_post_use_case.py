from __future__ import annotations

import pytest

from stui.port.event_models import ActionPostArg
from stui.port.run_port import (
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)
from stui.port.session_store_port import StoredSession
from stui.usecase.load_session_from_post_use_case import (
    LoadSessionFromPostStatus,
    LoadSessionFromPostUseCase,
)
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ActionPostItem,
    ConsoleScreenState,
    RunFinishedItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_load_session_from_post_loads_waiting_run() -> None:
    run_port = _RunPort(
        RunRuntimeStatus(
            run_id="waiting-run",
            status=RunRuntimeStatusKind.WAITING,
            wait_type=RunRuntimeWaitType.INPUT,
            prompt="Continue?",
        )
    )
    events_port = _EventsPort()
    session_store = _SessionStore()
    context = _context()
    state = _state("run_id=waiting-run")

    result = LoadSessionFromPostUseCase(
        run_port=run_port,
        events_port=events_port,
        session_store_port=session_store,
        context=context,
    ).execute(object(), state=state)

    assert result.status == LoadSessionFromPostStatus.LOADED
    assert result.state.session_key == "waiting-run"
    assert result.state.prompt.waiting_prompt == "Continue?"
    assert result.state.view_status.kind == ViewStatusKind.WAITING
    assert context.run_id == "waiting-run"
    assert context.status == RunStatus.WAITING_INPUT
    assert events_port.subscribe_calls == ["waiting-run"]
    assert session_store.written == [StoredSession(run_id="waiting-run", run_name="")]
    assert context.actions_done == {"post-1"}


def test_load_session_from_post_requires_intro_without_run_id() -> None:
    context = _context()

    result = LoadSessionFromPostUseCase(
        run_port=_RunPort(None),
        events_port=_EventsPort(),
        session_store_port=_SessionStore(),
        context=context,
    ).execute(object(), state=_state("run_id="))

    assert result.status == LoadSessionFromPostStatus.INTRO_REQUIRED
    assert result.state.session_key == "auth-run"
    assert context.actions_done == {"post-1"}


def test_load_session_from_post_errors_for_missing_run() -> None:
    context = _context()

    result = LoadSessionFromPostUseCase(
        run_port=_RunPort(None),
        events_port=_EventsPort(),
        session_store_port=_SessionStore(),
        context=context,
    ).execute(object(), state=_state("run_id=missing"))

    assert result.status == LoadSessionFromPostStatus.ERROR
    assert result.state.view_status.kind == ViewStatusKind.ERROR
    assert result.state.view_status.message == "Run 'missing' not found"
    assert context.actions_done == set()


def test_load_session_from_post_errors_for_finished_run() -> None:
    context = _context()

    result = LoadSessionFromPostUseCase(
        run_port=_RunPort(
            RunRuntimeStatus(run_id="done-run", status=RunRuntimeStatusKind.SUCCEEDED)
        ),
        events_port=_EventsPort(),
        session_store_port=_SessionStore(),
        context=context,
    ).execute(object(), state=_state("run_id=done-run"))

    assert result.status == LoadSessionFromPostStatus.ERROR
    assert result.state.view_status.kind == ViewStatusKind.ERROR
    assert result.state.view_status.message == "Run 'done-run' is not waiting"
    assert context.actions_done == set()


def _state(params: str) -> ConsoleScreenState:
    state = ConsoleScreenState(session_key="auth-run")
    state.transcript.items.append(
        RunFinishedItem(
            run_id="auth-run",
            status="succeeded",
            action=ActionPostItem(
                uid="post-1",
                type="post",
                label="Auth success",
                arg=ActionPostArg.LOAD_SESSION,
                params=params,
                auto=True,
            ),
        )
    )
    return state


def _context() -> RunEventContext:
    return RunEventContext(
        run_id="auth-run",
        run_name="auths/codex",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


class _RunPort:
    def __init__(self, status: RunRuntimeStatus | None) -> None:
        self.runtime_status = status

    def run(self, raw_args: str):  # noqa: ANN001
        raise AssertionError(f"unexpected run call: {raw_args}")

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        if self.runtime_status is None or self.runtime_status.run_id != run_id:
            return None
        return self.runtime_status


class _EventsPort:
    def __init__(self) -> None:
        self.subscribe_calls: list[str] = []

    def subscribe(
        self,
        *,
        run_id: str,
        listener: object,
        interval_seconds: float = 0.1,
    ) -> None:
        _ = listener, interval_seconds
        self.subscribe_calls.append(run_id)

    def unsubscribe(self) -> None:
        pass


class _SessionStore:
    def __init__(self) -> None:
        self.written: list[StoredSession] = []

    def read(self) -> StoredSession | None:
        return None

    def write(self, session: StoredSession) -> None:
        self.written.append(session)

    def clear(self) -> None:
        pass
