from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime

from rich.console import Group
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Static, TextArea

from stui.app_version import format_app_version
from stui.di.container import build_tui_container
from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.port.models_port import ModelsPortProviderItem
from stui.port.runs_port import RunsPortItem
from stui.screen.action_open_url_view import ActionOpenUrlView
from stui.screen.agent_context_stats_view import AgentContextStatsView
from stui.screen.autocomplete_view import AutoCompleteView
from stui.screen.footer_context_view import FooterContextView
from stui.screen.markdown import MarkdownView
from stui.screen.models_table_view import (
    ModelsTableModelRow,
    ModelsTableProviderRow,
    ModelsTableView,
)
from stui.screen.prompt import PromptController, PromptView
from stui.screen.runs_table_view import (
    RunRowStatus,
    RunsTableRow,
    RunsTableView,
    format_run_name,
)
from stui.screen.screen_status_view import ScreenStatusView
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme, build_textual_css
from stui.screen.transcript import RenderTranscript
from stui.screen.transcript_log import TranscriptLog
from stui.viewmodel.console_screen_event import InspectRunContextEvent
from stui.viewmodel.console_screen_state import ConsoleScreenState, PromptMode
from stui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel

_NARROW_FOOTER_WIDTH = 80


class ConsoleScreen(App[str]):
    CSS = build_textual_css()

    BINDINGS = [
        Binding("enter", "submit", show=False, priority=True),
        Binding("ctrl+j", "submit", show=False, priority=True),
        Binding("ctrl+q", "quit", show=False),
        Binding("ctrl+t", "toggle_agent_stats", show=False),
        Binding("escape", "handle_escape", show=False, priority=True),
        Binding("up", "transcript_scroll_up", show=False, priority=True),
        Binding("down", "transcript_scroll_down", show=False, priority=True),
        Binding("pageup", "transcript_page_up", show=False, priority=True),
        Binding("pagedown", "transcript_page_down", show=False, priority=True),
        Binding("home", "transcript_home", show=False, priority=True),
        Binding("end", "transcript_end", show=False, priority=True),
    ]

    def __init__(
        self,
        *,
        viewmodel: ConsoleScreenViewModel,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        strings: TuiStrings = DEFAULT_TUI_STRINGS,
    ) -> None:
        super().__init__(ansi_color=True)
        self.ui_theme = theme
        self.ui_strings = strings
        self.viewmodel = viewmodel
        self.state = ConsoleScreenState()
        self._render_transcript = RenderTranscript(strings=strings)
        self._last_runs_snapshot: tuple[RunsPortItem, ...] | None = None
        self._last_models_snapshot: tuple[ModelsPortProviderItem, ...] | None = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            TranscriptLog(
                id="transcript-log",
                auto_scroll=False,
                highlight=False,
                markup=False,
                min_width=0,
            ),
            Horizontal(
                ScreenStatusView(id="status", theme=self.ui_theme),
                Container(
                    Vertical(
                        ActionOpenUrlView(
                            id="notify-action",
                            theme=self.ui_theme,
                            strings=self.ui_strings,
                        ),
                        AgentContextStatsView(
                            id="agent-context-stats",
                            theme=self.ui_theme,
                            strings=self.ui_strings,
                        ),
                        id="right-status-stack",
                    ),
                    id="right-status-column",
                ),
                id="status-row",
            ),
            Container(
                RunsTableView(
                    id="runs-table",
                    visible=False,
                    empty_message=self.ui_strings.runs_table_empty_message,
                    navigation_hint=self.ui_strings.runs_table_navigation_hint,
                ),
                id="runs-table-area",
            ),
            Container(
                ModelsTableView(
                    id="models-table",
                    visible=False,
                    theme=self.ui_theme,
                    strings=self.ui_strings,
                ),
                id="models-table-area",
            ),
            AutoCompleteView(id="autocomplete", theme=self.ui_theme, visible=False),
            PromptView(theme=self.ui_theme),
            Container(
                Horizontal(
                    FooterContextView(
                        state=self.state.footer_context,
                        theme=self.ui_theme,
                        fallback_text=_build_footer_usage_text(state=self.state),
                        max_bar_width=30,
                        id="footer-wide-context",
                    ),
                    Static(
                        _build_footer_right_text(
                            state=self.state,
                            empty_icon=self.ui_theme.session_empty_icon,
                        ),
                        id="footer-wide-session",
                    ),
                    id="footer-wide",
                ),
                Vertical(
                    Static(
                        _build_footer_right_text(
                            state=self.state,
                            empty_icon=self.ui_theme.session_empty_icon,
                        ),
                        id="footer-narrow-session",
                    ),
                    FooterContextView(
                        state=self.state.footer_context,
                        theme=self.ui_theme,
                        fallback_text=_build_footer_usage_text(state=self.state),
                        id="footer-narrow-context",
                    ),
                    id="footer-narrow",
                ),
                id="footer",
            ),
            id="root",
        )

    async def on_mount(self) -> None:
        self.viewmodel.bind_on_state(self._on_state_changed)
        self.viewmodel.bind_on_event(self._on_viewmodel_event)
        await self.viewmodel.on_start()
        self._prompt_view().focus_prompt()

    def on_key(self, event: events.Key) -> None:
        if self._handle_notify_action_focus_key(event):
            return
        if self.state.models_table.visible and event.key == "right":
            self._models_table().focus_models()
            event.stop()
        elif self.state.models_table.visible and event.key == "left":
            self._models_table().focus_providers()
            event.stop()
        elif event.key == "up":
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

    def on_resize(self, _: events.Resize) -> None:
        if self._transcript_log().size.width <= 0:
            return
        self.set_timer(0.05, self.viewmodel.screen_resized)

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
        if self._focused_notify_action_done():
            self._done_notify_action()
            return
        if self._focused_notify_action_link():
            self._open_notify_action_link()
            return

        prompt = self._prompt()
        normalized_text = prompt.normalized_text()
        if self.state.runs_table.visible:
            self._runs_table().action_select_cursor()
            return

        if self.state.models_table.visible:
            await self._select_model_from_table()
            return

        if normalized_text.lower() in {"/quit", "/exit"}:
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
        if self.state.models_table.visible:
            self.viewmodel.hide_models_table()
            self._prompt_view().focus_prompt()
            return

        await self.viewmodel.interrupt_running_agent_turn()
        self._prompt_view().focus_prompt()

    async def action_toggle_agent_stats(self) -> None:
        await self.viewmodel.toggle_agent_stats()
        self._prompt_view().focus_prompt()

    def action_help_quit(self) -> None:
        pass

    def action_transcript_page_up(self) -> None:
        if self.state.runs_table.visible and self._runs_table().move_selection(-3):
            return
        self._transcript_log().scroll_page_up(animate=False, force=True)

    def action_transcript_scroll_up(self) -> None:
        if self.viewmodel.move_completion(-1):
            return
        if self.state.models_table.visible and self._models_table().move_selection(-1):
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
        if self.state.models_table.visible and self._models_table().move_selection(1):
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

    @on(DataTable.RowSelected, "#runs-table-data")
    def on_runs_table_row_selected(self, event: DataTable.RowSelected) -> None:
        runs_table = self._runs_table()
        if not runs_table.select_row(event.cursor_row):
            self._prompt_view().focus_prompt()
            return
        selected_run = runs_table.selected_run
        self.viewmodel.select_runs_table_row(
            prompt_text=self.state.runs_table.command,
            run_id=selected_run.run_id if selected_run is not None else "",
            run_name=selected_run.skill if selected_run is not None else "",
        )
        self._prompt_view().focus_prompt()

    @on(ActionOpenUrlView.OpenLink)
    def on_notify_action_open_link(self, event: ActionOpenUrlView.OpenLink) -> None:
        event.stop()
        self._open_notify_action_link()

    @on(ActionOpenUrlView.Done)
    def on_notify_action_done(self, event: ActionOpenUrlView.Done) -> None:
        event.stop()
        self._done_notify_action()

    def _focused_notify_action_link(self) -> bool:
        focused = self.focused
        if focused is None:
            return False
        return focused.id == "notify-action-open-link"

    def _focused_notify_action_done(self) -> bool:
        focused = self.focused
        if focused is None:
            return False
        return focused.id == "notify-action-done"

    def _focused_notify_action_button(self) -> bool:
        return self._focused_notify_action_link() or self._focused_notify_action_done()

    def _focused_prompt(self) -> bool:
        focused = self.focused
        if focused is None:
            return False
        return focused.id == "prompt"

    def _handle_notify_action_focus_key(self, event: events.Key) -> bool:
        if event.key not in {"left", "right"}:
            return False
        if self.state.notify_action is None:
            return False
        if self._focused_prompt() and event.key == "right":
            self.query_one("#notify-action-done", Button).focus()
            event.stop()
            return True
        if self._focused_notify_action_done() and event.key == "right":
            self.query_one("#notify-action-open-link", Button).focus()
            event.stop()
            return True
        if self._focused_notify_action_done() and event.key == "left":
            self._prompt_view().focus_prompt()
            event.stop()
            return True
        if self._focused_notify_action_link() and event.key == "left":
            self.query_one("#notify-action-done", Button).focus()
            event.stop()
            return True
        if self._focused_notify_action_link() and event.key == "right":
            self._prompt_view().focus_prompt()
            event.stop()
            return True
        return False

    def _open_notify_action_link(self) -> None:
        if self.state.notify_action is None:
            return
        notify_action = self.state.notify_action
        self.viewmodel.open_notify_action_link(
            run_id=notify_action.run_id,
            action_uid=notify_action.action.uid,
            url=notify_action.action.url,
        )
        self._prompt_view().focus_prompt()

    def _done_notify_action(self) -> None:
        if self.state.notify_action is None:
            return
        notify_action = self.state.notify_action
        self.viewmodel.done_notify_action(
            run_id=notify_action.run_id,
            action_uid=notify_action.action.uid,
        )
        self._prompt_view().focus_prompt()

    async def _select_model_from_table(self) -> None:
        models_table = self._models_table()
        if not models_table.models_focused:
            models_table.focus_models()
            return

        provider = models_table.selected_provider
        model = models_table.selected_model
        if provider is None or model is None:
            return

        await self.viewmodel.select_model(
            provider=provider.name,
            model=model.name,
        )

    def _refresh_status(self, *, new_state: ConsoleScreenState) -> None:
        try:
            status = self.query_one("#status", ScreenStatusView)
        except NoMatches:
            return
        status.set_state(new_state.view_status)

    def _refresh_footer(self, *, new_state: ConsoleScreenState) -> None:
        try:
            footer_wide = self.query_one("#footer-wide", Horizontal)
            footer_narrow = self.query_one("#footer-narrow", Vertical)
            wide_context = self.query_one("#footer-wide-context", FooterContextView)
            wide_session = self.query_one("#footer-wide-session", Static)
            narrow_session = self.query_one("#footer-narrow-session", Static)
            narrow_context = self.query_one("#footer-narrow-context", FooterContextView)
        except NoMatches:
            return

        usage_text = _build_footer_usage_text(state=new_state)
        session_text = _build_footer_right_text(
            state=new_state,
            empty_icon=self.ui_theme.session_empty_icon,
        )
        wide_context.set_state(new_state.footer_context, fallback_text=usage_text)
        wide_session.update(session_text)
        narrow_session.update(session_text)
        narrow_context.set_state(new_state.footer_context, fallback_text=usage_text)

        is_narrow = self.size.width < _NARROW_FOOTER_WIDTH
        footer_wide.display = not is_narrow
        footer_narrow.display = is_narrow

    def _refresh_notify_action(self, *, new_state: ConsoleScreenState) -> None:
        try:
            notify_action = self.query_one("#notify-action", ActionOpenUrlView)
        except NoMatches:
            return
        notify_action.set_state(new_state.notify_action)

    def _refresh_agent_context_stats(self, *, new_state: ConsoleScreenState) -> None:
        try:
            agent_context_stats = self.query_one(
                "#agent-context-stats",
                AgentContextStatsView,
            )
        except NoMatches:
            return
        agent_context_stats.set_state(new_state.agent_context_stats)

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
                style=self.ui_theme.color_text_accent,
            )
        )
        transcript.write(
            Group(
                Text(""),
                Text("[inspect] RunContext"),
                MarkdownView(
                    _render_json_markdown_block(_build_run_context_payload(event)),
                    theme=self.ui_theme,
                ).render(),
                Text(""),
                Text("[inspect] ScreenStatus"),
                MarkdownView(
                    _render_json_markdown_block(_build_screen_state_payload(self.state)),
                    theme=self.ui_theme,
                ).render(),
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
        self._refresh_models_table(new_state=new_state)
        self._refresh_table_visibility(new_state=new_state)
        self._refresh_prompt(new_state=new_state)
        self._refresh_status(new_state=new_state)
        self._refresh_notify_action(new_state=new_state)
        self._refresh_agent_context_stats(new_state=new_state)
        self._refresh_autocomplete(new_state=new_state)
        self._refresh_footer(new_state=new_state)

    def _refresh_prompt(self, *, new_state: ConsoleScreenState) -> None:
        self._prompt_view().set_prompt_state(state=new_state.prompt)

    def _refresh_autocomplete(self, *, new_state: ConsoleScreenState) -> None:
        autocomplete = self._autocomplete_view()
        autocomplete.set_state(
            new_state.autocompletion,
            reserve_space=new_state.prompt.text.startswith("/"),
        )

    def _refresh_transcript(self, *, new_state: ConsoleScreenState) -> None:
        transcript = self._transcript_log()
        renderables = self._render_transcript.render(
            items=new_state.transcript.items,
            mode=new_state.transcript.mode,
            theme=self.ui_theme,
            prompt_placeholder="",
        )
        with self.batch_update():
            transcript.clear()
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

    def _refresh_models_table(self, *, new_state: ConsoleScreenState) -> None:
        if (
            self._last_models_snapshot is not None
            and new_state.models_table.rows == self._last_models_snapshot
        ):
            return
        models_table = self._models_table()
        models_table.set_rows(
            [
                ModelsTableProviderRow(
                    name=provider.name,
                    source=provider.source,
                    models=tuple(
                        ModelsTableModelRow(name=model.name, active=model.active)
                        for model in provider.models
                    ),
                )
                for provider in new_state.models_table.rows
            ]
        )
        self._last_models_snapshot = new_state.models_table.rows

    def _refresh_table_visibility(self, *, new_state: ConsoleScreenState) -> None:
        try:
            runs_table_area = self.query_one("#runs-table-area", Container)
            runs_table = self.query_one("#runs-table", RunsTableView)
            models_table_area = self.query_one("#models-table-area", Container)
            models_table = self.query_one("#models-table", ModelsTableView)
            status_row = self.query_one("#status-row", Horizontal)
        except NoMatches:
            return

        prompt_panel_visible = new_state.prompt.mode in {
            PromptMode.AUTOCOMPLETION,
            PromptMode.RUNS_TABLE,
            PromptMode.MODELS_TABLE,
        }
        runs_table_area.display = new_state.runs_table.visible
        runs_table.display = new_state.runs_table.visible
        models_table_area.display = new_state.models_table.visible
        models_table.display = new_state.models_table.visible
        status_row.display = not prompt_panel_visible

    def _runs_table(self) -> RunsTableView:
        return self.query_one("#runs-table", RunsTableView)

    def _models_table(self) -> ModelsTableView:
        return self.query_one("#models-table", ModelsTableView)

    def _run_list_item_to_row(self, run: RunsPortItem) -> RunsTableRow:
        return RunsTableRow(
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
    strings: TuiStrings = DEFAULT_TUI_STRINGS,
) -> str:
    resolved_strings = _resolve_runtime_strings(strings)
    container = build_tui_container(theme=theme, strings=resolved_strings)
    viewmodel = container.build_viewmodel(session_key=session_key)

    class ThemedConsoleScreen(ConsoleScreen):
        CSS = build_textual_css(theme)

    app = ThemedConsoleScreen(
        viewmodel=viewmodel,
        theme=theme,
        strings=container.strings,
    )
    result = app.run(mouse=False)
    return result or session_key


def _resolve_runtime_strings(strings: TuiStrings) -> TuiStrings:
    if strings.intro_hint:
        return strings
    return replace(strings, intro_hint=format_app_version())


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


def _format_agent_tokens(value: int) -> str:
    if value < 1000:
        return str(value)
    return f"{value / 1000:.1f}k"


def _build_footer_usage_text(*, state: ConsoleScreenState) -> str:
    if state.agent_usage is None:
        return "/ for commands"
    return (
        f"{state.agent_usage.model}\n"
        f"{_format_agent_tokens(state.agent_usage.total_tokens)}"
    )


def _build_footer_right_text(*, state: ConsoleScreenState, empty_icon: str) -> str:
    run_id = state.session_key.strip()
    if not run_id or run_id == "main":
        return empty_icon

    run_name = state.run_name
    if not run_name:
        return run_id
    return f"{run_id}\n{format_run_name(run_name)}"


def _is_local_dev_status_command(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized == "/dev"


def _build_run_context_payload(event: InspectRunContextEvent) -> dict[str, object]:
    return {
        "run_id": event.run_id,
        "run_name": event.run_name,
        "status": event.status.value,
        "max_page": event.max_page,
    }


def _build_screen_state_payload(state: ConsoleScreenState) -> dict[str, object]:
    return {
        "session_key": state.session_key,
        "run_name": state.run_name,
        "transcript": {
            "mode": state.transcript.mode.value,
            "items_count": len(state.transcript.items),
        },
        "prompt": {
            "mode": state.prompt.mode.value,
            "text": state.prompt.text,
            "cursor_position": state.prompt.cursor_position,
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
