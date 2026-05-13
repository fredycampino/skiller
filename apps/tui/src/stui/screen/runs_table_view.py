from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rich.text import Text
from textual import events
from textual._context import NoActiveAppError
from textual.widgets import DataTable


class RunRowMode(StrEnum):
    FLOW = "flow"
    CHAT = "chat"


class RunRowStatus(StrEnum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_WEBHOOK = "waiting_webhook"
    WAITING_CHANNEL = "waiting_channel"
    FAILED = "failed"
    SUCCESS = "success"


@dataclass(frozen=True)
class RunsTableRow:
    mode: RunRowMode
    status: RunRowStatus
    skill: str
    updated_at: str
    run_id: str


_MOCK_RUN_ROWS: tuple[RunsTableRow, ...] = (
    RunsTableRow(
        mode=RunRowMode.CHAT,
        status=RunRowStatus.WAITING_INPUT,
        skill="wait_input_test",
        updated_at="05-04 00:01",
        run_id="run-2026-05-04-000123",
    ),
    RunsTableRow(
        mode=RunRowMode.FLOW,
        status=RunRowStatus.RUNNING,
        skill="webhook_signal_oracle",
        updated_at="05-04 00:02",
        run_id="run-2026-05-04-000456",
    ),
    RunsTableRow(
        mode=RunRowMode.CHAT,
        status=RunRowStatus.SUCCESS,
        skill="chat",
        updated_at="05-04 00:03",
        run_id="run-2026-05-04-000789",
    ),
    RunsTableRow(
        mode=RunRowMode.FLOW,
        status=RunRowStatus.FAILED,
        skill="cleanup_job",
        updated_at="05-04 00:04",
        run_id="run-2026-05-04-000246",
    ),
)


class RunsTableView(DataTable):
    def __init__(
        self,
        *,
        visible: bool = True,
        id: str | None = None,
        ) -> None:
        super().__init__(
            id=id,
            show_header=True,
            show_row_labels=False,
            zebra_stripes=False,
            cursor_type="row",
            cursor_foreground_priority="css",
            cursor_background_priority="css",
        )
        self.display = visible
        self.show_horizontal_scrollbar = False
        self.show_vertical_scrollbar = False
        self._rows: tuple[RunsTableRow, ...] = _MOCK_RUN_ROWS
        self._selected_index = 0

    def on_mount(self) -> None:
        self._render_rows()

    def on_resize(self, _: events.Resize) -> None:
        self._render_rows()

    def set_rows(self, rows: list[RunsTableRow]) -> None:
        self._rows = tuple(rows)
        if not self._rows:
            self._selected_index = 0
        else:
            self._selected_index = max(0, min(self._selected_index, len(self._rows) - 1))
        self._render_rows()

    @property
    def selected_run(self) -> RunsTableRow | None:
        if not self._display_rows():
            return None
        if self._selected_index < 0 or self._selected_index >= len(self._display_rows()):
            return None
        return self._rows[self._selected_index]

    def move_selection(self, delta: int) -> bool:
        if not self._display_rows():
            return False
        selected_index = self._selected_index + delta
        if selected_index < 0:
            selected_index = 0
        elif selected_index >= len(self._display_rows()):
            selected_index = len(self._display_rows()) - 1
        self._selected_index = selected_index
        if self.is_mounted:
            self.move_cursor(row=self._selected_index)
        return True

    def move_to_start(self) -> bool:
        if not self._display_rows():
            return False
        self._selected_index = 0
        if self.is_mounted:
            self.move_cursor(row=0)
        return True

    def move_to_end(self) -> bool:
        if not self._display_rows():
            return False
        self._selected_index = len(self._display_rows()) - 1
        if self.is_mounted:
            self.move_cursor(row=self._selected_index)
        return True

    def _render_rows(self) -> None:
        try:
            _ = self.app
        except NoActiveAppError:
            return

        self.clear(columns=True)
        updated_width, status_width, skill_width, run_id_width = self._column_widths()
        self.add_column("Updated", width=updated_width)
        self.add_column("Status", width=status_width)
        self.add_column("Skill", width=skill_width)
        self.add_column("Run ID", width=run_id_width)
        for row in self._rows:
            self.add_row(
                row.updated_at,
                format_run_row_status(row),
                row.skill,
                Text(row.run_id, justify="right"),
                key=row.run_id,
            )
        if self._display_rows():
            self.move_cursor(row=self._selected_index)

    def _column_widths(self) -> tuple[int, int, int, int]:
        updated_width = max(
            len("Updated"),
            max((len(row.updated_at) for row in self._display_rows()), default=0),
        )
        status_width = max(
            len("Status"),
            max((len(format_run_row_status(row)) for row in self._display_rows()), default=0),
        ) + 2
        run_id_width = max(
            len("Run ID"),
            max((len(row.run_id) for row in self._display_rows()), default=0),
        )
        skill_min_width = max(
            len("Skill"),
            max((len(row.skill) for row in self._display_rows()), default=0),
        )
        available_width = max(self.size.width - 6, 0)
        if available_width > 0:
            skill_width = max(
                available_width - status_width - updated_width - run_id_width,
                skill_min_width,
            )
        else:
            skill_width = skill_min_width
        return updated_width, status_width, skill_width, run_id_width

    def _display_rows(self) -> tuple[RunsTableRow, ...]:
        return self._rows


def format_run_row_status(row: RunsTableRow) -> str:
    if row.status == RunRowStatus.WAITING_INPUT:
        return "waiting-i"
    if row.status == RunRowStatus.WAITING_WEBHOOK:
        return "waiting-w"
    if row.status == RunRowStatus.WAITING_CHANNEL:
        return "waiting-c"
    return row.status.value
