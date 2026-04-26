from __future__ import annotations

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Static, TextArea

from skiller.interfaces.tui.adapter.default_run_port import DefaultRunPort
from skiller.interfaces.tui.screen.prompt import PromptController
from skiller.interfaces.tui.screen.render import render_transcript
from skiller.interfaces.tui.screen.screen_status_view import ScreenStatusView
from skiller.interfaces.tui.screen.theme import DEFAULT_TUI_THEME, TuiTheme, build_textual_css
from skiller.interfaces.tui.screen.transcript_log import TranscriptLog
from skiller.interfaces.tui.viewmodel.console_screen_state import ConsoleScreenState
from skiller.interfaces.tui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel


class ConsoleScreen(App[str]):
    CSS = build_textual_css()

    BINDINGS = [
        Binding("enter", "submit", show=False, priority=True),
        Binding("ctrl+j", "submit", show=False, priority=True),
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
        self.state: ConsoleScreenState = viewmodel.state
        self._follow_transcript = True
        self._last_renderable_count = -1
        self._last_transcript_empty = False

    def compose(self) -> ComposeResult:
        yield Vertical(
            TranscriptLog(id="transcript-log", auto_scroll=False, highlight=False, markup=False),
            ScreenStatusView(id="status", theme=self.ui_theme),
            Horizontal(
                Static(self.ui_theme.cursor, id="prompt-prefix"),
                TextArea(
                    "",
                    id="prompt",
                    placeholder=self.ui_theme.prompt_placeholder,
                    soft_wrap=True,
                    compact=True,
                    show_line_numbers=False,
                    highlight_cursor_line=False,
                ),
                id="prompt-row",
            ),
            Static(self._build_footer_text(), id="footer"),
            id="root",
        )

    def on_mount(self) -> None:
        self.viewmodel.bind_on_change(self._refresh_from_state)
        self._refresh_status()
        self._refresh_transcript(scroll_to_end=True, force_scroll=True)
        self._refresh_footer()
        self._prompt().focus()

    def on_unmount(self) -> None:
        self.viewmodel.stop_observing()

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

    async def action_submit(self) -> None:
        result = await self.viewmodel.submit(self._prompt().normalized_text())
        if result.should_exit:
            self.exit(self.state.session_key)
            return

        if result.clear_prompt:
            self._prompt().clear()
        self._refresh_from_state(force_scroll=True)
        if result.observe_run_id:
            self.viewmodel.start_observing(result.observe_run_id)
        self._prompt().focus()

    def action_transcript_page_up(self) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        transcript_log.scroll_page_up(animate=False)
        self._follow_transcript = False

    def action_transcript_scroll_up(self) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        transcript_log.action_scroll_up()
        self._follow_transcript = False

    def action_transcript_page_down(self) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        transcript_log.scroll_page_down(animate=False)
        self._follow_transcript = transcript_log.is_vertical_scroll_end

    def action_transcript_scroll_down(self) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        transcript_log.action_scroll_down()
        self._follow_transcript = transcript_log.is_vertical_scroll_end

    def action_transcript_home(self) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        transcript_log.scroll_home(animate=False)
        self._follow_transcript = False

    def action_transcript_end(self) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        transcript_log.scroll_end(animate=False)
        self._follow_transcript = True

    def _refresh_status(self) -> None:
        try:
            status = self.query_one("#status", ScreenStatusView)
        except NoMatches:
            return
        status.set_status(self.state.screen_status)

    def _refresh_transcript(self, *, scroll_to_end: bool, force_scroll: bool = False) -> None:
        transcript_log = self.query_one("#transcript-log", TranscriptLog)
        was_at_end = transcript_log.is_vertical_scroll_end
        renderables = render_transcript(
            items=self.state.transcript_items,
            prompt_placeholder=self.ui_theme.prompt_placeholder,
        )
        renderable_count = len(renderables)
        is_empty = len(self.state.transcript_items) == 0
        should_scroll_end = scroll_to_end and (
            force_scroll or self._follow_transcript or was_at_end
        )

        can_append = (
            not is_empty
            and not self._last_transcript_empty
            and self._last_renderable_count >= 0
            and renderable_count >= self._last_renderable_count
        )
        if can_append and renderable_count > self._last_renderable_count:
            append_renderables = renderables[self._last_renderable_count :]
            for renderable in append_renderables:
                transcript_log.write(renderable, scroll_end=should_scroll_end)
        else:
            transcript_log.clear()
            for renderable in renderables:
                transcript_log.write(renderable, scroll_end=should_scroll_end)

        self._last_renderable_count = renderable_count
        self._last_transcript_empty = is_empty
        if scroll_to_end and (force_scroll or self._follow_transcript or was_at_end):
            self._follow_transcript = True

    def _refresh_footer(self) -> None:
        try:
            footer = self.query_one("#footer", Static)
        except NoMatches:
            return
        footer.update(self._build_footer_text())

    def _build_footer_text(self) -> str:
        return "/quit exit"

    def _prompt(self) -> PromptController:
        return PromptController(self.query_one("#prompt", TextArea))

    def _refresh_from_state(self, force_scroll: bool = False) -> None:
        self._refresh_status()
        self._refresh_transcript(scroll_to_end=True, force_scroll=force_scroll)
        self._refresh_footer()


def run_console_screen(
    *,
    session_key: str,
    theme: TuiTheme = DEFAULT_TUI_THEME,
) -> str:
    viewmodel = ConsoleScreenViewModel(
        session_key=session_key,
        run_port=DefaultRunPort(),
    )

    class ThemedConsoleScreen(ConsoleScreen):
        CSS = build_textual_css(theme)

    app = ThemedConsoleScreen(viewmodel=viewmodel, theme=theme)
    result = app.run(mouse=False)
    return result or session_key
