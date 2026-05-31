from __future__ import annotations

from dataclasses import dataclass

import pytest

from stui.port.event_models import LogEvent
from stui.port.event_port import LogEventsListener
from stui.port.run_port import (
    RunDispatch,
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.usecase.select_runs_table_row_use_case import SelectRunsTableRowUseCase
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    RunStepItem,
    StepNotifyOutputItem,
    TranscriptMode,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


@dataclass
class FakeLogEventsListener(LogEventsListener):
    def notify(self, events: list[LogEvent]) -> None:
        _ = events

    def get_max_page(self) -> int:
        return 100


class FakeRunPort:
    def __init__(self, runtime_status: RunRuntimeStatus | None = None) -> None:
        self.runtime_status = runtime_status
        self.run_calls: list[str] = []
        self.status_calls: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        self.run_calls.append(raw_args)
        raise AssertionError(f"unexpected run call: {raw_args}")

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        self.status_calls.append(run_id)
        return self.runtime_status

class FakeEventsPort:
    def __init__(self, *, current_run_id: str = "", current_listener: object | None = None) -> None:
        self.subscribe_calls: list[str] = []
        self.unsubscribe_calls = 0
        self.current_run_id = current_run_id
        self.current_listener = current_listener

    def subscribe(self, *, run_id: str, listener: FakeLogEventsListener) -> None:
        if self.current_listener is not None:
            self.unsubscribe()
        self.current_listener = listener
        self.current_run_id = run_id
        self.subscribe_calls.append(run_id)

    def unsubscribe(self) -> None:
        self.unsubscribe_calls += 1
        self.current_listener = None
        self.current_run_id = ""


def test_unknown_command_only_closes_table() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status())
    events_port = FakeEventsPort()

    result = _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/agents",
        run_id="run-1234",
        run_name="ant",
    )

    assert result.state.runs_table.visible is False
    assert result.state.runs_table.command == ""
    assert run_port.status_calls == []
    assert context.run_id == "old-run"
    assert events_port.subscribe_calls == []
    assert events_port.unsubscribe_calls == 0


def test_empty_run_id_only_closes_table() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status())
    events_port = FakeEventsPort()

    result = _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="",
        run_name="ant",
    )

    assert result.state.runs_table.visible is False
    assert result.state.runs_table.command == ""
    assert run_port.status_calls == []
    assert context.run_id == "old-run"
    assert events_port.subscribe_calls == []


def test_missing_runtime_status_only_closes_table() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(runtime_status=None)
    events_port = FakeEventsPort()

    result = _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="ant",
    )

    assert result.state.runs_table.visible is False
    assert result.state.runs_table.command == ""
    assert run_port.status_calls == ["run-1234"]
    assert context.run_id == "old-run"
    assert events_port.subscribe_calls == []
    assert events_port.unsubscribe_calls == 0


def test_non_waiting_runtime_status_only_closes_table() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(
        RunRuntimeStatus(run_id="run-1234", status=RunRuntimeStatusKind.SUCCEEDED)
    )
    events_port = FakeEventsPort(current_run_id="old-run", current_listener=observer)

    result = _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="ant",
    )

    assert result.state.runs_table.visible is False
    assert result.state.session_key == "main"
    assert context.run_id == "old-run"
    assert events_port.current_run_id == "old-run"
    assert events_port.subscribe_calls == []
    assert events_port.unsubscribe_calls == 0


def test_existing_observer_is_unsubscribed_before_waiting_run_is_observed() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status())
    events_port = FakeEventsPort(current_run_id="old-run", current_listener=observer)

    _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="ant",
    )

    assert events_port.unsubscribe_calls == 1
    assert events_port.current_run_id == "run-1234"
    assert events_port.subscribe_calls == ["run-1234"]


def test_runs_selection_loads_waiting_run_in_chat_mode() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status(wait_type=RunRuntimeWaitType.INPUT))
    events_port = FakeEventsPort()

    result = _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="ant",
    )

    assert result.state.session_key == "run-1234"
    assert result.state.run_name == "ant"
    assert result.state.transcript.mode == TranscriptMode.CHAT
    assert result.state.view_status.kind == ViewStatusKind.WAITING
    assert result.state.prompt.waiting_prompt == "Write a message"
    assert context.run_id == "run-1234"
    assert context.run_name == "ant"
    assert context.mode == RunMode.CHAT
    assert context.status == RunStatus.WAITING_INPUT
    assert events_port.subscribe_calls == ["run-1234"]


def test_same_run_selection_preserves_transcript_items() -> None:
    state = _state_with_open_table()
    state.load_session(run_id="run-1234")
    transcript_items = [
        RunStepItem(run_id="run-1234", step_type="notify", step_id="intro"),
        StepNotifyOutputItem(run_id="run-1234", step_type="notify", message="Skiller.run"),
    ]
    state.set_transcript(mode=TranscriptMode.CHAT, items=transcript_items)
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status(wait_type=RunRuntimeWaitType.INPUT))
    events_port = FakeEventsPort()

    result = _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="steps",
    )

    assert result.state.session_key == "run-1234"
    assert result.state.run_name == "steps"
    assert result.state.transcript.mode == TranscriptMode.CHAT
    assert result.state.transcript.items == transcript_items
    assert context.mode == RunMode.CHAT
    assert events_port.subscribe_calls == ["run-1234"]


def test_waiting_webhook_status_loads_run() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status(wait_type=RunRuntimeWaitType.WEBHOOK))
    events_port = FakeEventsPort()

    _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="ant",
    )

    assert context.status == RunStatus.WAITING_WEBHOOK
    assert state.view_status.kind == ViewStatusKind.WAITING
    assert events_port.subscribe_calls == ["run-1234"]


def test_waiting_channel_status_loads_run() -> None:
    state = _state_with_open_table()
    context = _context()
    observer = FakeLogEventsListener()
    run_port = FakeRunPort(_waiting_status(wait_type=RunRuntimeWaitType.CHANNEL))
    events_port = FakeEventsPort()

    _use_case(run_port=run_port, events_port=events_port, context=context).execute(
        observer,
        state=state,
        prompt_text="/runs",
        run_id="run-1234",
        run_name="ant",
    )

    assert context.status == RunStatus.WAITING_CHANNEL
    assert state.view_status.kind == ViewStatusKind.WAITING
    assert events_port.subscribe_calls == ["run-1234"]


def _use_case(
    *,
    run_port: FakeRunPort,
    events_port: FakeEventsPort,
    context: RunEventContext,
) -> SelectRunsTableRowUseCase:
    return SelectRunsTableRowUseCase(
        run_port=run_port,
        events_port=events_port,
        context=context,
    )


def _state_with_open_table() -> ConsoleScreenState:
    state = ConsoleScreenState()
    state.runs_table.visible = True
    state.runs_table.command = "/runs"
    return state


def _context() -> RunEventContext:
    return RunEventContext(
        run_id="old-run",
        run_name="old-skill",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _waiting_status(
    *,
    wait_type: RunRuntimeWaitType = RunRuntimeWaitType.INPUT,
) -> RunRuntimeStatus:
    return RunRuntimeStatus(
        run_id="run-1234",
        status=RunRuntimeStatusKind.WAITING,
        wait_type=wait_type,
        prompt="Write a message",
    )
