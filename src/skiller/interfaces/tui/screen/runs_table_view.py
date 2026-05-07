from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual import events
from textual._context import NoActiveAppError
from textual.widgets import DataTable


@dataclass(frozen=True)
class RunsTableRow:
    status: str
    skill: str
    run_id: str


_MOCK_RUN_ROWS: tuple[RunsTableRow, ...] = (
    RunsTableRow(
        status="waiting",
        skill="wait_input_test",
        run_id="run-2026-05-04-000123",
    ),
    RunsTableRow(
        status="running",
        skill="webhook_signal_oracle",
        run_id="run-2026-05-04-000456",
    ),
    RunsTableRow(
        status="succeeded",
        skill="chat",
        run_id="run-2026-05-04-000789",
    ),
    RunsTableRow(
        status="failed",
        skill="cleanup_job",
        run_id="run-2026-05-04-000246",
    ),
)

_EXIT_ROW = RunsTableRow(status="", skill="exit", run_id="")
_EXIT_ROW_KEY = "__exit__"


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
        self._rows = tuple(
            RunsTableRow(
                status=row.status.lower(),
                skill=row.skill,
                run_id=row.run_id,
            )
            for row in rows
        )
        self._selected_index = min(self._selected_index, len(self._display_rows()) - 1)
        self._render_rows()

    @property
    def selected_run(self) -> RunsTableRow | None:
        if not self._display_rows():
            return None
        if self._selected_index < 0 or self._selected_index >= len(self._display_rows()):
            return None
        if self._selected_index == len(self._rows):
            return None
        return self._rows[self._selected_index]

    @property
    def selected_is_exit(self) -> bool:
        return bool(self._display_rows()) and self._selected_index == len(self._rows)

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
        status_width, skill_width, run_id_width = self._column_widths()
        self.add_column("Status", width=status_width)
        self.add_column("Skill", width=skill_width)
        self.add_column("Run ID", width=run_id_width)
        for row in self._rows:
            self.add_row(
                row.status.lower(),
                row.skill,
                Text(row.run_id, justify="right"),
                key=row.run_id,
            )
        self.add_row(
            _EXIT_ROW.status,
            _EXIT_ROW.skill,
            Text(_EXIT_ROW.run_id, justify="right"),
            key=_EXIT_ROW_KEY,
        )
        if self._display_rows():
            self.move_cursor(row=self._selected_index)

    def _column_widths(self) -> tuple[int, int, int]:
        status_width = max(
            len("Status"),
            max((len(row.status) for row in self._display_rows()), default=0),
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
                available_width - status_width - run_id_width,
                skill_min_width,
            )
        else:
            skill_width = skill_min_width
        return status_width, skill_width, run_id_width

    def _display_rows(self) -> tuple[RunsTableRow, ...]:
        return self._rows + (_EXIT_ROW,)
