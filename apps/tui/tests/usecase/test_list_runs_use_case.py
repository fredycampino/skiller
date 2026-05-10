from __future__ import annotations

import asyncio

import pytest
import stui.usecase.list_runs_use_case as list_runs_use_case_module
from stui.usecase.list_runs_use_case import ListRunsUseCase
from stui.usecase.normalize_command_use_case import (
    NormalizeCommandUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    UserInputItem,
    ViewStatusKind,
)

from apps.tui.tests.support import (
    FakeRunsPort,
    make_runs_port_item,
    patched_to_thread,
)

pytestmark = pytest.mark.unit


def test_list_runs_use_case_returns_query_rows() -> None:
    async def run() -> None:
        port = FakeRunsPort()
        state = ConsoleScreenState(session_key="main")
        use_case = ListRunsUseCase(runs_port=port)

        result = await use_case.execute(
            state=state,
            command=NormalizeCommandUseCase().execute(text="/runs waiting"),
            limit=5,
        )

        assert port.called_with == [(5, ["waiting"])]
        assert result.state is state
        assert state.runs_table.visible is True
        assert state.view_status.kind == ViewStatusKind.HIDDEN
        assert state.runs_table.rows == tuple(port.runs)
        assert isinstance(state.transcript.items[0], UserInputItem)
        assert state.transcript.items[0].text == "/runs waiting"

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_list_runs_use_case_maps_runtime_errors_to_state() -> None:
    async def run() -> None:
        port = FakeRunsPort(error=RuntimeError("runs command failed"))
        state = ConsoleScreenState(session_key="main")
        use_case = ListRunsUseCase(runs_port=port)

        result = await use_case.execute(
            state=state,
            command=NormalizeCommandUseCase().execute(text="/runs"),
        )

        assert port.called_with == [(20, [])]
        assert result.state is state
        assert state.runs_table.visible is False
        assert state.view_status.kind == ViewStatusKind.ERROR
        assert state.runs_table.rows == ()
        assert isinstance(state.transcript.items[0], UserInputItem)
        assert isinstance(state.transcript.items[1], DispatchErrorItem)
        assert state.transcript.items[1].message == "error: runs command failed"

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_list_runs_use_case_filters_waiting_input_runs_for_chats_command() -> None:
    async def run() -> None:
        port = FakeRunsPort(
            runs=[
                make_runs_port_item(run_id="run-input", wait_type="input"),
                make_runs_port_item(
                    run_id="run-webhook",
                    current="wait_signal",
                    wait_type="webhook",
                ),
            ]
        )
        state = ConsoleScreenState(session_key="main")
        use_case = ListRunsUseCase(runs_port=port)

        result = await use_case.execute(
            state=state,
            command=NormalizeCommandUseCase().execute(text="/chats"),
        )

        assert result.state is state
        assert port.called_with == [(20, ["WAITING"])]
        assert [item.id for item in state.runs_table.rows] == ["run-input"]
        assert state.runs_table.command == "/chats"

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())
