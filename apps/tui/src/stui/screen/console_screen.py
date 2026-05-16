from __future__ import annotations

import json
from datetime import datetime

from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable, Static, TextArea

from stui.di.container import build_tui_container
from stui.port.runs_port import RunsPortItem
from stui.screen.autocomplete_view import AutoCompleteView
from stui.screen.prompt import PromptController, PromptView
from stui.screen.runs_table_view import (
    RunRowMode,
    RunRowStatus,
    RunsTableRow,
    RunsTableView,
)
from stui.screen.screen_status_view import ScreenStatusView
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme, build_textual_css
from stui.screen.transcript import RenderTranscript
from stui.screen.transcript_log import TranscriptLog
from stui.viewmodel.console_screen_event import InspectRunContextEvent
from stui.viewmodel.console_screen_state import ConsoleScreenState
from stui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel


class ConsoleScreen(App[str]):
    CSS = build_textual_css()

    BINDINGS = [
        Binding("enter", "submit", show=False, priority=True),
        Binding("ctrl+j", "submit", show=False, priority=True),
        Binding("escape", "handle_escape", show=False, priority=True),
        Binding("up", "transcript_scroll_up", show=False, priority=True),
        Binding("down", "transcript_scroll_down", show=False, priority=True),
        Binding("pageup", "transcript_page_up", show=False, priority=True),
        Binding("pagedown", "transcript_page_down", show=False, priority=True),
        Binding("home", "transcript_home", show=False, priority=True),
        Binding("end", "transcript_end", show=False, priority=True),
        Binding("ctrl+c", "quit", show=False),
    ]

    def __init__(
        self,
        *,
        viewmodel: ConsoleScreenViewModel,
        theme: TuiTheme = DEFAULT_TUI_THEME,
    ) -> None:
        super().__init__(ansi_color=True)
        self.ui_theme = theme
        self.viewmodel = viewmodel
        self.state = ConsoleScreenState()
        self._render_transcript = RenderTranscript()
        self._last_runs_snapshot: tuple[RunsPortItem, ...] | None = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            TranscriptLog(id="transcript-log", auto_scroll=False, highlight=False, markup=False),
            Container(
                RunsTableView(id="runs-table", visible=False),
                id="runs-table-area",
            ),
            ScreenStatusView(id="status", theme=self.ui_theme),
            PromptView(theme=self.ui_theme),
            AutoCompleteView(id="autocomplete", theme=self.ui_theme, visible=False),
            Horizontal(
                Static(self._build_footer_left_text(), id="footer-left"),
                Static(self._build_footer_right_text(), id="footer-right"),
                id="footer",
            ),
            id="root",
        )

    def on_mount(self) -> None:
        self.viewmodel.bind_on_state(self._on_state_changed)
        self.viewmodel.bind_on_event(self._on_viewmodel_event)
        self._prompt_view().focus_prompt()

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            self.action_transcript_scroll_up()
            event.stop()
        elif event.key == "down":
            self.action_transcript_scroll_down()
            event.stop()
        elif event.key == "pageup":
            self.action_transcript_page_up()
            event.stop()
        elif event.key == "pagedown":
            self.action_transcript_page_down()
            event.stop()
        elif event.key == "home":
            self.action_transcript_home()
            event.stop()
        elif event.key == "end":
            self.action_transcript_end()
            event.stop()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.action_transcript_scroll_up()
        event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self.action_transcript_scroll_down()
        event.stop()

    @on(TextArea.Changed, "#prompt")
    def on_prompt_changed(self, message: TextArea.Changed) -> None:
        if self._prompt_view().consume_programmatic_change():
            return
        prompt = self._prompt()
        self.viewmodel.prompt_change(
            text=prompt.text(),
            cursor_position=prompt.cursor_position(),
        )

    async def action_submit(self) -> None:
        prompt = self._prompt()
        normalized_text = prompt.normalized_text()
        if self.state.runs_table.visible:
            self._runs_table().action_select_cursor()
            return

        if normalized_text.lower() in {"/quit", "quit", "exit"}:
            self.exit(self.state.session_key)
            return

        if _is_local_dev_status_command(normalized_text):
            self.viewmodel.inspect_run_context()
            self._prompt_view().focus_prompt()
            return

        await self.viewmodel.prompt_enter()
        self._prompt_view().focus_prompt()

    async def action_handle_escape(self) -> None:
        if self.state.runs_table.visible:
            self.viewmodel.hide_runs_table()
            self._prompt_view().focus_prompt()
            return

        await self.viewmodel.interrupt_running_agent_turn()
        self._prompt_view().focus_prompt()

    def action_transcript_page_up(self) -> None:
        if self.state.runs_table.visible and self._runs_table().move_selection(-3):
            return
        self._transcript_log().scroll_page_up(animate=False, force=True)

    def action_transcript_scroll_up(self) -> None:
        if self.viewmodel.move_completion(-1):
            return
        if self.state.runs_table.visible and self._runs_table().move_selection(-1):
            return
        self._transcript_log().scroll_up(animate=False, force=True, immediate=True)

    def action_transcript_page_down(self) -> None:
        if self.state.runs_table.visible and self._runs_table().move_selection(3):
            return
        self._transcript_log().scroll_page_down(animate=False, force=True)

    def action_transcript_scroll_down(self) -> None:
        if self.viewmodel.move_completion(1):
            return
        if self.state.runs_table.visible and self._runs_table().move_selection(1):
            return
        self._transcript_log().scroll_down(animate=False, force=True, immediate=True)

    def action_transcript_home(self) -> None:
        if self.state.runs_table.visible and self._runs_table().move_to_start():
            return
        self._transcript_log().scroll_home(animate=False, force=True, immediate=True)

    def action_transcript_end(self) -> None:
        if self.state.runs_table.visible and self._runs_table().move_to_end():
            return
        self._transcript_log().scroll_end(animate=False, force=True, immediate=True)

    @on(DataTable.RowSelected, "#runs-table")
    def on_runs_table_row_selected(self, _: DataTable.RowSelected) -> None:
        runs_table = self._runs_table()
        selected_run = runs_table.selected_run
        self.viewmodel.select_runs_table_row(
            prompt_text=self.state.runs_table.command,
            run_id=selected_run.run_id if selected_run is not None else "",
            skill_name=selected_run.skill if selected_run is not None else "",
        )
        self._prompt_view().focus_prompt()

    def _refresh_status(self, *, new_state: ConsoleScreenState) -> None:
        try:
            status = self.query_one("#status", ScreenStatusView)
        except NoMatches:
            return
        status.set_state(
            new_state.view_status,
            waiting_prompt=new_state.prompt.waiting_prompt,
        )

    def _refresh_footer(self, *, new_state: ConsoleScreenState) -> None:
        try:
            footer_left = self.query_one("#footer-left", Static)
            footer_right = self.query_one("#footer-right", Static)
        except NoMatches:
            return
        footer_left.update(self._build_footer_left_text())
        footer_right.update(self._build_footer_right_text(state=new_state))

    def _build_footer_left_text(self) -> str:
        return "/ for commands"

    def _build_footer_right_text(self, *, state: ConsoleScreenState | None = None) -> str:
        screen_state = state or self.state
        session_key = screen_state.session_key.strip()
        if not session_key or session_key == "main":
            return self.ui_theme.session_empty_icon
        return session_key

    def _prompt(self) -> PromptController:
        return self._prompt_view().controller()

    def _prompt_view(self) -> PromptView:
        return self.query_one("#prompt-row", PromptView)

    def _autocomplete_view(self) -> AutoCompleteView:
        return self.query_one("#autocomplete", AutoCompleteView)

    def _transcript_log(self) -> TranscriptLog:
        return self.query_one("#transcript-log", TranscriptLog)

    def _append_run_context_inspection(self, *, event: InspectRunContextEvent) -> None:
        transcript = self._transcript_log()

        if transcript.lines:
            transcript.write(Text(""))
        transcript.write(
            Text(
                f"{self.ui_theme.user_icon} /dev",
                style=self.ui_theme.rich_style(self.ui_theme.color_text_accent),
            )
        )
        transcript.write(
            Group(
                Text(""),
                Text("[inspect] RunContext"),
                Markdown(_render_json_markdown_block(_build_run_context_payload(event))),
                Text(""),
                Text("[inspect] ScreenStatus"),
                Markdown(_render_json_markdown_block(_build_screen_state_payload(self.state))),
            ),
            scroll_end=True,
        )

    def _refresh_from_state(
        self,
        *,
        new_state: ConsoleScreenState,
    ) -> None:
        self._refresh_transcript(new_state=new_state)
        self._refresh_runs_table(new_state=new_state)
        self._refresh_runs_visibility(new_state=new_state)
        self._refresh_prompt(new_state=new_state)
        self._refresh_status(new_state=new_state)
        self._refresh_autocomplete(new_state=new_state)
        self._refresh_footer(new_state=new_state)

    def _refresh_prompt(self, *, new_state: ConsoleScreenState) -> None:
        self._prompt_view().set_prompt_state(state=new_state.prompt)

    def _refresh_autocomplete(self, *, new_state: ConsoleScreenState) -> None:
        autocomplete = self._autocomplete_view()
        autocomplete.set_state(new_state.autocompletion)

    def _refresh_transcript(self, *, new_state: ConsoleScreenState) -> None:
        transcript = self._transcript_log()
        transcript.clear()
        renderables = self._render_transcript.render(
            items=new_state.transcript.items,
            mode=new_state.transcript.mode,
            theme=self.ui_theme,
            prompt_placeholder="",
        )
        for index, renderable in enumerate(renderables):
            transcript.write(
                renderable,
                expand=True,
                scroll_end=index == len(renderables) - 1,
            )

    def _refresh_runs_table(self, *, new_state: ConsoleScreenState) -> None:
        if (
            self._last_runs_snapshot is not None
            and new_state.runs_table.rows == self._last_runs_snapshot
        ):
            return
        runs_table = self._runs_table()
        runs_table.set_rows(
            [
                self._run_list_item_to_row(run)
                for run in new_state.runs_table.rows
            ]
        )
        self._last_runs_snapshot = new_state.runs_table.rows

    def _refresh_runs_visibility(self, *, new_state: ConsoleScreenState) -> None:
        try:
            runs_table_area = self.query_one("#runs-table-area", Container)
            runs_table = self.query_one("#runs-table", RunsTableView)
            status = self.query_one("#status", ScreenStatusView)
        except NoMatches:
            return

        runs_table_area.display = new_state.runs_table.visible
        runs_table.display = new_state.runs_table.visible
        status.display = not new_state.runs_table.visible

    def _runs_table(self) -> RunsTableView:
        return self.query_one("#runs-table", RunsTableView)

    def _run_list_item_to_row(self, run: RunsPortItem) -> RunsTableRow:
        return RunsTableRow(
            mode=_resolve_run_row_mode(run),
            status=_resolve_run_row_status(run),
            skill=run.ref,
            updated_at=_format_run_updated_at(run.updated_at),
            run_id=run.id,
        )

    def _on_state_changed(self, state: ConsoleScreenState) -> None:
        self._refresh_from_state(new_state=state)
        self.state = state

    def _on_viewmodel_event(self, event: InspectRunContextEvent) -> None:
        self._append_run_context_inspection(event=event)


def run_console_screen(
    *,
    session_key: str,
    theme: TuiTheme = DEFAULT_TUI_THEME,
) -> str:
    container = build_tui_container(theme=theme)
    viewmodel = container.build_viewmodel(session_key=session_key)

    class ThemedConsoleScreen(ConsoleScreen):
        CSS = build_textual_css(theme)

    app = ThemedConsoleScreen(viewmodel=viewmodel, theme=theme)
    result = app.run(mouse=False)
    return result or session_key


def _resolve_run_row_mode(run: RunsPortItem) -> RunRowMode:
    normalized_wait_type = str(run.wait_type or "").strip().lower()
    if normalized_wait_type == "input":
        return RunRowMode.CHAT
    return RunRowMode.FLOW


def _resolve_run_row_status(run: RunsPortItem) -> RunRowStatus:
    normalized_status = run.status.strip().lower()
    normalized_wait_type = str(run.wait_type or "").strip().lower()
    if normalized_status == "waiting":
        if normalized_wait_type == "input":
            return RunRowStatus.WAITING_INPUT
        if normalized_wait_type == "channel":
            return RunRowStatus.WAITING_CHANNEL
        return RunRowStatus.WAITING_WEBHOOK
    if normalized_status == "failed":
        return RunRowStatus.FAILED
    if normalized_status == "succeeded":
        return RunRowStatus.SUCCESS
    return RunRowStatus.RUNNING


def _format_run_updated_at(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return "-"

    parsers = (
        lambda text: datetime.strptime(text, "%Y-%m-%d %H:%M:%S"),
        lambda text: datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ"),
        lambda text: datetime.fromisoformat(text.replace("Z", "+00:00")),
    )
    for parse in parsers:
        try:
            return parse(normalized).strftime("%m-%d %H:%M")
        except ValueError:
            continue
    return "-"


def _is_local_dev_status_command(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized == "/dev"


def _build_run_context_payload(event: InspectRunContextEvent) -> dict[str, object]:
    return {
        "run_id": event.run_id,
        "skill_name": event.skill_name,
        "status": event.status.value,
        "max_page": event.max_page,
    }


def _build_screen_state_payload(state: ConsoleScreenState) -> dict[str, object]:
    return {
        "session_key": state.session_key,
        "transcript": {
            "mode": state.transcript.mode.value,
            "items_count": len(state.transcript.items),
        },
        "prompt": {
            "mode": state.prompt.mode.value,
            "text": state.prompt.text,
            "cursor_position": state.prompt.cursor_position,
            "waiting_prompt": state.prompt.waiting_prompt,
        },
        "runs_table": {
            "visible": state.runs_table.visible,
            "command": state.runs_table.command,
            "rows_count": len(state.runs_table.rows),
        },
        "view_status": {
            "kind": state.view_status.kind.value,
            "message": state.view_status.message,
        },
        "autocompletion": _build_autocompletion_payload(state),
    }


def _build_autocompletion_payload(
    state: ConsoleScreenState,
) -> dict[str, object] | None:
    completion = state.autocompletion
    if completion is None:
        return None
    return {
        "visible": completion.visible,
        "query": completion.query,
        "items_count": len(completion.items),
        "selected_index": completion.selected_index,
        "replace_from": completion.replace_from,
        "replace_to": completion.replace_to,
    }


def _render_json_markdown_block(payload: dict[str, object]) -> str:
    return f"```json\n{json.dumps(payload, ensure_ascii=True, indent=2)}\n```"
