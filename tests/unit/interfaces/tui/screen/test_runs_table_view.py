from __future__ import annotations

import pytest

from skiller.interfaces.tui.screen.runs_table_view import RunsTableRow, RunsTableView

pytestmark = pytest.mark.unit


def test_runs_table_view_uses_mock_rows_and_selection() -> None:
    table = RunsTableView(id="runs-table")

    assert table.show_horizontal_scrollbar is False
    assert table.show_vertical_scrollbar is False
    assert table.allow_horizontal_scroll is False
    assert table.allow_vertical_scroll is False
    assert table.selected_run is not None
    assert table.selected_run.status == "waiting"

    table.set_rows(
        [
            RunsTableRow(status="WAITING", skill="wait_input_test", run_id="run-1234"),
            RunsTableRow(status="RUNNING", skill="webhook_signal_oracle", run_id="run-4567"),
        ]
    )

    assert table.selected_run is not None
    assert table.selected_run.status == "waiting"

    assert table.move_selection(1) is True
    assert table.selected_run is not None
    assert table.selected_run.status == "running"

    assert table.move_selection(-1) is True
    assert table.selected_run is not None
    assert table.selected_run.status == "waiting"

    assert table.move_to_end() is True
    assert table.selected_run is None
    assert table.selected_is_exit is True

    assert table.move_selection(-1) is True
    assert table.selected_run is not None
    assert table.selected_run.status == "running"
    assert table.selected_is_exit is False

    assert table.move_to_start() is True
    assert table.selected_run is not None
    assert table.selected_run.run_id == "run-1234"
