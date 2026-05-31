from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rich.text import Text
from textual import events
from textual._context import NoActiveAppError
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static


class RunRowStatus(StrEnum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_WEBHOOK = "waiting_webhook"
    WAITING_CHANNEL = "waiting_channel"
    FAILED = "failed"
    SUCCESS = "success"


@dataclass(frozen=True)
class RunsTableRow:
    status: RunRowStatus
    skill: str
    updated_at: str
    run_id: str


class RunsTableView(Vertical):
    def __init__(
        self,
        *,
        empty_message: str,
        navigation_hint: str,
        visible: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._table = DataTable(
            id="runs-table-data",
            show_header=True,
            show_row_labels=False,
            zebra_stripes=False,
            cursor_type="row",
            cursor_foreground_priority="css",
            cursor_background_priority="css",
        )
        self.display = visible
        self._table.show_horizontal_scrollbar = False
        self._table.show_vertical_scrollbar = False
        self._rows: tuple[RunsTableRow, ...] = ()
        self._empty_message = empty_message
        self._selected_index = 0
        self._navigation_hint = navigation_hint

    def compose(self) -> ComposeResult:
        yield self._table
        yield Static(
            Text(self._empty_message, justify="center"),
            id="runs-table-empty",
        )
        yield Static("", id="runs-table-selected-flow")
        yield Static(Text(self._navigation_hint), id="runs-table-navigation")

    def on_mount(self) -> None:
        self._render_rows()

    def on_resize(self, _: events.Resize) -> None:
        self._render_rows()

    def set_rows(self, rows: list[RunsTableRow]) -> None:
        self._rows = tuple(rows)
        self._selected_index = self._first_loadable_index() or 0
        self._render_rows()

    @property
    def selected_run(self) -> RunsTableRow | None:
        if not self._rows:
            return None
        if self._selected_index < 0 or self._selected_index >= len(self._rows):
            return None
        row = self._rows[self._selected_index]
        if not is_run_row_loadable(row):
            return None
        return row

    def select_row(self, row_index: int) -> bool:
        if row_index < 0 or row_index >= len(self._rows):
            return False
        if not is_run_row_loadable(self._rows[row_index]):
            if self.is_mounted and self.selected_run is not None:
                self._table.move_cursor(row=self._selected_index)
            return False
        self._selected_index = row_index
        if self.is_mounted:
            self._table.move_cursor(row=self._selected_index)
            self._refresh_selected_flow()
        return True

    def move_selection(self, delta: int) -> bool:
        selected_index = self._next_loadable_index(delta=delta)
        if selected_index is None:
            return False
        self._selected_index = selected_index
        if self.is_mounted:
            self._table.move_cursor(row=self._selected_index)
            self._refresh_selected_flow()
        return True

    def move_to_start(self) -> bool:
        selected_index = self._first_loadable_index()
        if selected_index is None:
            return False
        self._selected_index = selected_index
        if self.is_mounted:
            self._table.move_cursor(row=self._selected_index)
            self._refresh_selected_flow()
        return True

    def move_to_end(self) -> bool:
        selected_index = self._last_loadable_index()
        if selected_index is None:
            return False
        self._selected_index = selected_index
        if self.is_mounted:
            self._table.move_cursor(row=self._selected_index)
            self._refresh_selected_flow()
        return True

    def action_select_cursor(self) -> None:
        if self.selected_run is None:
            return
        self._table.action_select_cursor()

    def _render_rows(self) -> None:
        try:
            _ = self.app
        except NoActiveAppError:
            return

        self._table.clear(columns=True)
        updated_width, status_width, skill_width, run_id_width = self._column_widths()
        self._table.add_column("Updated", width=updated_width)
        self._table.add_column("Status", width=status_width)
        self._table.add_column("Flow", width=skill_width)
        self._table.add_column(Text("Run ID", justify="right"), width=run_id_width)
        self.query_one("#runs-table-empty", Static).display = not self._rows
        self._refresh_selected_flow()
        if not self._rows:
            return
        for row in self._rows:
            self._table.add_row(
                row.updated_at,
                format_run_row_status(row),
                format_run_name(row.skill),
                Text(row.run_id, justify="right"),
                key=row.run_id,
            )
        if self.selected_run is not None:
            self._table.move_cursor(row=self._selected_index)
            self._refresh_selected_flow()

    def _column_widths(self) -> tuple[int, int, int, int]:
        updated_width = max(
            len("Updated"),
            max((len(row.updated_at) for row in self._rows), default=0),
        )
        status_width = max(
            len("Status"),
            max((len(format_run_row_status(row)) for row in self._rows), default=0),
        ) + 2
        run_id_width = max(
            len("Run ID") + 2,
            max((len(row.run_id) for row in self._rows), default=0),
        )
        skill_min_width = max(
            len("Flow"),
            max((len(format_run_name(row.skill)) for row in self._rows), default=0),
        )
        available_width = max(self.size.width - 10, 0)
        if available_width > 0:
            skill_width = max(
                available_width - status_width - updated_width - run_id_width,
                skill_min_width,
            )
        else:
            skill_width = skill_min_width
        return updated_width, status_width, skill_width, run_id_width

    def _refresh_selected_flow(self) -> None:
        selected_run = self.selected_run
        selected_flow = selected_run.skill if selected_run is not None else ""
        selected_flow_view = self.query_one("#runs-table-selected-flow", Static)
        selected_flow_view.display = selected_run is not None
        selected_flow_view.update(selected_flow)

    def _first_loadable_index(self) -> int | None:
        for index, row in enumerate(self._rows):
            if is_run_row_loadable(row):
                return index
        return None

    def _last_loadable_index(self) -> int | None:
        index = len(self._rows) - 1
        while index >= 0:
            if is_run_row_loadable(self._rows[index]):
                return index
            index -= 1
        return None

    def _next_loadable_index(self, *, delta: int) -> int | None:
        if delta == 0:
            return self._selected_index if self.selected_run is not None else None
        step = 1 if delta > 0 else -1
        remaining = abs(delta)
        index = self._selected_index
        while remaining > 0:
            index += step
            while 0 <= index < len(self._rows) and not is_run_row_loadable(self._rows[index]):
                index += step
            if index < 0 or index >= len(self._rows):
                return self._selected_index if self.selected_run is not None else None
            remaining -= 1
        return index


def format_run_row_status(row: RunsTableRow) -> str:
    if row.status == RunRowStatus.WAITING_INPUT:
        return "waiting-i"
    if row.status == RunRowStatus.WAITING_WEBHOOK:
        return "waiting-w"
    if row.status == RunRowStatus.WAITING_CHANNEL:
        return "waiting-c"
    return row.status.value


def format_run_name(run_name: str) -> str:
    if "/" not in run_name:
        return run_name
    return f"/{run_name.rsplit('/', maxsplit=1)[-1]}"


def is_run_row_loadable(row: RunsTableRow) -> bool:
    return row.status in {
        RunRowStatus.WAITING_INPUT,
        RunRowStatus.WAITING_WEBHOOK,
        RunRowStatus.WAITING_CHANNEL,
    }
