from __future__ import annotations

import pytest
from stui.port.run_port import CommandAck, CommandAckStatus
from stui.screen.runs_table_view import RunRowMode, RunRowStatus
from stui.usecase.run_event_context import (
    RunEventContext,
    RunStatus,
)
from stui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    PromptState,
    RunsTableState,
    ViewStatusKind,
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
        runs_table=RunsTableState(visible=True, command="/runs"),
    )

    result = SelectRunsTableRowUseCase(
        run_port=FakeRunPort(),
        context=context,
    ).execute(
        observer,
        state=state,
        prompt_text="/runs",
        mode=RunRowMode.FLOW,
        status=RunRowStatus.SUCCESS,
        run_id="",
        skill_name="",
        is_exit=True,
    )

    assert result.state is state
    assert state.runs_table.visible is False
    assert state.runs_table.command == ""


def test_select_runs_table_row_use_case_closes_table_for_non_waiting_rows() -> None:
    observer = FakeObserver(run_id="run-old")
    run_port = FakeRunPort()
    context = RunEventContext(
        run_id="run-old",
        skill_name="old-skill",
        status=RunStatus.RUNNING,
    )
    state = ConsoleScreenState(
        session_key="main",
        runs_table=RunsTableState(visible=True, command="/runs"),
    )

    result = SelectRunsTableRowUseCase(
        run_port=run_port,
        context=context,
    ).execute(
        observer,
        state=state,
        prompt_text="/runs waiting",
        mode=RunRowMode.FLOW,
        status=RunRowStatus.FAILED,
        run_id="run-1",
        skill_name="run-1-skill",
        is_exit=False,
    )

    assert result.state is state
    assert state.runs_table.visible is False
    assert observer.run_id == "run-old"
    assert run_port.unsubscribed == []
    assert run_port.subscribed == []


def test_select_runs_table_row_use_case_activates_waiting_input_for_chats_command() -> None:
    observer = FakeObserver(run_id="run-old")
    run_port = FakeRunPort()
    context = RunEventContext(
        run_id="run-old",
        skill_name="old-skill",
        status=RunStatus.RUNNING,
    )
    state = ConsoleScreenState(
        session_key="main",
        runs_table=RunsTableState(visible=True, command="/chats"),
        prompt=PromptState(
            text="old",
            cursor_position=3,
            waiting_prompt="old prompt",
        ),
    )

    result = SelectRunsTableRowUseCase(
        run_port=run_port,
        context=context,
    ).execute(
        observer,
        state=state,
        prompt_text="",
        mode=RunRowMode.CHAT,
        status=RunRowStatus.WAITING_INPUT,
        run_id="run-1234",
        skill_name="wait_input_test",
        is_exit=False,
    )

    assert result.state is state
    assert state.runs_table.visible is False
    assert state.runs_table.command == ""
    assert state.prompt.text == ""
    assert state.prompt.cursor_position == 0
    assert state.prompt.waiting_prompt == ""
    assert state.session_key == "run-1234"
    assert state.view_status.kind == ViewStatusKind.RUNNING
    assert observer.run_id == "run-1234"
    assert context.run_id == "run-1234"
    assert context.skill_name == "wait_input_test"
    assert context.status == RunStatus.RUNNING
    assert run_port.unsubscribed == [observer]
    assert run_port.subscribed == [observer]
