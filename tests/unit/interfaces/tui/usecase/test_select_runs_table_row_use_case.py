from __future__ import annotations

import pytest

from skiller.interfaces.tui.port.run_port import CommandAck, CommandAckStatus
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from skiller.interfaces.tui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    ScreenStatus,
)

pytestmark = pytest.mark.unit


class FakeRunPort:
    def __init__(self) -> None:
        self.subscribed: list[object] = []
        self.unsubscribed: list[object] = []

    def run(self, raw_args: str) -> CommandAck:
        _ = raw_args
        return CommandAck(status=CommandAckStatus.ACCEPTED)

    def subscribe(self, observer: object) -> None:
        self.subscribed.append(observer)

    def unsubscribe(self, observer: object) -> None:
        self.unsubscribed.append(observer)


class FakeObserver:
    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id


def test_select_runs_table_row_use_case_closes_table_for_exit() -> None:
    observer = FakeObserver()
    context = RunEventContext()
    state = ConsoleScreenState(
        session_key="main",
        runs_table_visible=True,
        runs_table_command="/runs",
    )

    result = SelectRunsTableRowUseCase(
        run_port=FakeRunPort(),
        context=context,
    ).execute(
        observer,
        state=state,
        prompt_text="/runs",
        status="",
        run_id="",
        skill_name="",
        is_exit=True,
    )

    assert result.state is state
    assert state.runs_table_visible is False
    assert state.runs_table_command == ""


def test_select_runs_table_row_use_case_closes_table_for_non_waiting_rows() -> None:
    observer = FakeObserver(run_id="run-old")
    run_port = FakeRunPort()
    context = RunEventContext(
        run_id="run-old",
        skill_name="old-skill",
        mode=RunMode.FLOW,
        status=RunStatus.RUNNING,
    )
    state = ConsoleScreenState(
        session_key="main",
        runs_table_visible=True,
        runs_table_command="/runs",
    )

    result = SelectRunsTableRowUseCase(
        run_port=run_port,
        context=context,
    ).execute(
        observer,
        state=state,
        prompt_text="/runs waiting",
        status="failed",
        run_id="run-1",
        skill_name="run-1-skill",
        is_exit=False,
    )

    assert result.state is state
    assert state.runs_table_visible is False
    assert observer.run_id == "run-old"
    assert run_port.unsubscribed == []
    assert run_port.subscribed == []


def test_select_runs_table_row_use_case_activates_waiting_input_for_agents_command() -> None:
    observer = FakeObserver(run_id="run-old")
    run_port = FakeRunPort()
    context = RunEventContext(
        run_id="run-old",
        skill_name="old-skill",
        mode=RunMode.FLOW,
        status=RunStatus.RUNNING,
    )
    state = ConsoleScreenState(
        session_key="main",
        runs_table_visible=True,
        runs_table_command="/agents",
        prompt_text="old",
        prompt_cursor_position=3,
        waiting_prompt="old prompt",
    )

    result = SelectRunsTableRowUseCase(
        run_port=run_port,
        context=context,
    ).execute(
        observer,
        state=state,
        prompt_text="",
        status="waiting-i",
        run_id="run-1234",
        skill_name="wait_input_test",
        is_exit=False,
    )

    assert result.state is state
    assert state.runs_table_visible is False
    assert state.runs_table_command == ""
    assert state.prompt_text == ""
    assert state.prompt_cursor_position == 0
    assert state.waiting_prompt == ""
    assert state.session_key == "run-1234"
    assert state.screen_status == ScreenStatus.RUNNING
    assert observer.run_id == "run-1234"
    assert context.run_id == "run-1234"
    assert context.skill_name == "wait_input_test"
    assert context.mode == RunMode.FLOW
    assert context.status == RunStatus.RUNNING
    assert run_port.unsubscribed == [observer]
    assert run_port.subscribed == [observer]
