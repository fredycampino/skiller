from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from stui.screen.footer_context_view import FooterContextView
from stui.screen.run_name import format_run_name
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import AgentMetricsState

NARROW_FOOTER_WIDTH = 80


@dataclass(frozen=True)
class FooterState:
    session_key: str
    run_name: str | None
    metrics: AgentMetricsState | None


class FooterView(Container):
    def __init__(
        self,
        *,
        session_key: str,
        run_name: str | None,
        metrics: AgentMetricsState | None,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._theme = theme
        self._state = _footer_state(
            session_key=session_key,
            run_name=run_name,
            metrics=metrics,
        )

    def compose(self) -> ComposeResult:
        session_text = _build_footer_session_text(
            session_key=self._state.session_key,
            run_name=self._state.run_name,
            empty_icon=self._theme.session_empty_icon,
        )
        is_narrow = self.app.size.width < NARROW_FOOTER_WIDTH
        wide = Horizontal(
            FooterContextView(
                metrics=self._state.metrics,
                theme=self._theme,
                max_bar_width=30,
                id="footer-wide-context",
            ),
            Static(session_text, id="footer-wide-session"),
            id="footer-wide",
        )
        wide.display = not is_narrow
        yield wide

        narrow = Vertical(
            Static(session_text, id="footer-narrow-session"),
            FooterContextView(
                metrics=self._state.metrics,
                theme=self._theme,
                id="footer-narrow-context",
            ),
            id="footer-narrow",
        )
        narrow.display = is_narrow
        yield narrow

    def on_mount(self) -> None:
        self._sync_layout()

    def on_resize(self, _: events.Resize) -> None:
        self._sync_layout()

    def set_state(
        self,
        *,
        session_key: str,
        run_name: str | None,
        metrics: AgentMetricsState | None,
    ) -> None:
        state = _footer_state(
            session_key=session_key,
            run_name=run_name,
            metrics=metrics,
        )
        if state == self._state:
            return
        self._state = state
        if not self.is_mounted:
            return

        session_text = _build_footer_session_text(
            session_key=state.session_key,
            run_name=state.run_name,
            empty_icon=self._theme.session_empty_icon,
        )
        self.query_one("#footer-wide-session", Static).update(session_text)
        self.query_one("#footer-narrow-session", Static).update(session_text)
        self.query_one("#footer-wide-context", FooterContextView).set_state(
            metrics=state.metrics,
        )
        self.query_one("#footer-narrow-context", FooterContextView).set_state(
            metrics=state.metrics,
        )

    def _sync_layout(self) -> None:
        if not self.is_mounted:
            return
        is_narrow = self.app.size.width < NARROW_FOOTER_WIDTH
        self.query_one("#footer-wide", Horizontal).display = not is_narrow
        self.query_one("#footer-narrow", Vertical).display = is_narrow


def _footer_state(
    *,
    session_key: str,
    run_name: str | None,
    metrics: AgentMetricsState | None,
) -> FooterState:
    metrics_snapshot = None
    if metrics is not None:
        metrics_snapshot = AgentMetricsState(
            usage=metrics.usage,
            context=metrics.context,
        )
    return FooterState(
        session_key=session_key,
        run_name=run_name,
        metrics=metrics_snapshot,
    )


def _build_footer_session_text(
    *,
    session_key: str,
    run_name: str | None,
    empty_icon: str,
) -> str:
    run_id = session_key.strip()
    if not run_id or run_id == "main":
        return empty_icon
    if not run_name:
        return run_id
    return f"{run_id}\n{format_run_name(run_name)}"
