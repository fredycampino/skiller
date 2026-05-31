from __future__ import annotations

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from stui.screen.runs_table_view import (
    RunRowStatus,
    RunsTableRow,
    RunsTableView,
    format_run_name,
    is_run_row_loadable,
)
from stui.screen.theme import build_textual_css

pytestmark = pytest.mark.unit


def test_runs_table_view_uses_rows_and_selection() -> None:
    table = _runs_table()

    table.set_rows(
        [
            RunsTableRow(
                status=RunRowStatus.SUCCESS,
                skill="completed_flow",
                updated_at="05-04 00:00",
                run_id="run-0000",
            ),
            RunsTableRow(
                status=RunRowStatus.WAITING_INPUT,
                skill="wait_input_test",
                updated_at="05-04 00:01",
                run_id="run-1234",
            ),
            RunsTableRow(
                status=RunRowStatus.RUNNING,
                skill="webhook_signal_oracle",
                updated_at="05-04 00:02",
                run_id="run-4567",
            ),
            RunsTableRow(
                status=RunRowStatus.WAITING_WEBHOOK,
                skill="webhook_signal_oracle",
                updated_at="05-04 00:03",
                run_id="run-8910",
            ),
        ]
    )

    assert table.selected_run is not None
    assert table.selected_run.status == RunRowStatus.WAITING_INPUT

    assert table.move_selection(1) is True
    assert table.selected_run is not None
    assert table.selected_run.status == RunRowStatus.WAITING_WEBHOOK

    assert table.move_selection(-1) is True
    assert table.selected_run is not None
    assert table.selected_run.status == RunRowStatus.WAITING_INPUT

    assert table.move_to_end() is True
    assert table.selected_run is not None
    assert table.selected_run.status == RunRowStatus.WAITING_WEBHOOK

    assert table.move_selection(-1) is True
    assert table.selected_run is not None
    assert table.selected_run.status == RunRowStatus.WAITING_INPUT

    assert table.move_to_start() is True
    assert table.selected_run is not None
    assert table.selected_run.run_id == "run-1234"


def test_runs_table_view_keeps_empty_state_without_selection() -> None:
    table = _runs_table()

    table.set_rows([])

    assert table.selected_run is None
    assert table.move_selection(1) is False
    assert table.move_to_start() is False
    assert table.move_to_end() is False


def test_runs_table_view_does_not_select_terminal_rows() -> None:
    table = _runs_table()
    table.set_rows(
        [
            RunsTableRow(
                status=RunRowStatus.SUCCESS,
                skill="done",
                updated_at="05-04 00:01",
                run_id="run-1234",
            ),
            RunsTableRow(
                status=RunRowStatus.FAILED,
                skill="failed",
                updated_at="05-04 00:02",
                run_id="run-4567",
            ),
            RunsTableRow(
                status=RunRowStatus.RUNNING,
                skill="running",
                updated_at="05-04 00:03",
                run_id="run-8910",
            ),
        ]
    )

    assert table.selected_run is None
    assert table.select_row(0) is False
    assert table.select_row(1) is False
    assert table.select_row(2) is False
    assert table.move_selection(1) is False
    assert table.move_to_start() is False
    assert table.move_to_end() is False


def test_runs_table_view_keeps_selection_on_real_rows() -> None:
    table = _runs_table()
    table.set_rows(
        [
            RunsTableRow(
                status=RunRowStatus.WAITING_INPUT,
                skill="wait_input_test",
                updated_at="05-04 00:01",
                run_id="run-1234",
            )
        ]
    )

    assert table.move_selection(1) is True
    assert table.selected_run is not None
    assert table.selected_run.run_id == "run-1234"


def test_runs_table_view_formats_run_name_paths() -> None:
    assert format_run_name("mono") == "mono"
    assert format_run_name("apps/tui/tests/flows/notify/notify.yaml") == "/notify.yaml"


def test_runs_table_view_renders_selected_flow_expansion_row() -> None:
    async def run() -> None:
        app = _RunsTableHarness()
        async with app.run_test() as pilot:
            table = app.query_one(RunsTableView)
            selected_flow = app.query_one("#runs-table-selected-flow", Static)

            table.set_rows(
                [
                    RunsTableRow(
                        status=RunRowStatus.WAITING_INPUT,
                        skill="apps/tui/tests/flows/notify/notify.yaml",
                        updated_at="05-04 00:01",
                        run_id="run-1234",
                    ),
                    RunsTableRow(
                        status=RunRowStatus.WAITING_WEBHOOK,
                        skill="mono",
                        updated_at="05-04 00:02",
                        run_id="run-4567",
                    ),
                ]
            )
            await pilot.pause()

            assert str(selected_flow.content) == "apps/tui/tests/flows/notify/notify.yaml"

            table.move_selection(1)
            await pilot.pause()

            assert str(selected_flow.content) == "mono"

    asyncio.run(run())


def test_runs_table_view_identifies_loadable_rows() -> None:
    assert is_run_row_loadable(
        RunsTableRow(
            status=RunRowStatus.WAITING_INPUT,
            skill="input",
            updated_at="05-04 00:01",
            run_id="run-1",
        )
    )
    assert is_run_row_loadable(
        RunsTableRow(
            status=RunRowStatus.WAITING_WEBHOOK,
            skill="webhook",
            updated_at="05-04 00:01",
            run_id="run-2",
        )
    )
    assert not is_run_row_loadable(
        RunsTableRow(
            status=RunRowStatus.SUCCESS,
            skill="done",
            updated_at="05-04 00:01",
            run_id="run-3",
        )
    )


def _runs_table() -> RunsTableView:
    return RunsTableView(
        id="runs-table",
        empty_message="No runs yet. Use /run to execute your flows.",
        navigation_hint="↑↓ · Enter · Esc",
    )


class _RunsTableHarness(App[None]):
    CSS = build_textual_css()

    def compose(self) -> ComposeResult:
        yield _runs_table()
