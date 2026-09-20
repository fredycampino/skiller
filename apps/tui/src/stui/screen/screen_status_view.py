from __future__ import annotations

from rich.text import Text
from textual.timer import Timer
from textual.widgets import Static

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import (
    ViewStatusKind,
    ViewStatusState,
)


class ScreenStatusView(Static):
    def __init__(
        self,
        *,
        state: ViewStatusState | None = None,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        initial_state = state or ViewStatusState()
        self._state = ViewStatusState(
            kind=initial_state.kind,
            message=initial_state.message,
        )
        self._theme = theme
        self._frame_index = 0
        self._timer: Timer | None = None
        self._rendered_state: tuple[ViewStatusKind, str] | None = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(
            self._theme.status_animation_interval,
            self._tick,
            pause=True,
        )
        self._sync_timer()
        self._refresh()

    def set_state(self, state: ViewStatusState) -> None:
        state_values = (state.kind, state.message)
        current_values = (self._state.kind, self._state.message)
        if state_values == current_values:
            return
        self._state = ViewStatusState(kind=state.kind, message=state.message)
        self._sync_timer()
        self._refresh()

    def _refresh(self) -> None:
        rendered_state = (self._state.kind, self._state.message)
        if rendered_state == self._rendered_state:
            return
        self.update(self.render())
        self._rendered_state = rendered_state

    def _tick(self) -> None:
        self._frame_index = (self._frame_index + 1) % len(self._theme.status_spinner_frames)
        self.update(self.render())

    def _sync_timer(self) -> None:
        if self._timer is None:
            return
        if self._state.kind == ViewStatusKind.RUNNING:
            self._timer.resume()
            return
        self._timer.pause()

    def render(self) -> Text | str:
        if self._state.kind == ViewStatusKind.HIDDEN:
            return ""
        if self._state.kind == ViewStatusKind.RUNNING:
            frame = self._theme.status_spinner_frames[self._frame_index]
            return f"{frame} Running"
        if self._state.kind == ViewStatusKind.WAITING:
            waiting_style = f"{self._theme.color_text_secondary} dim"
            message = self._state.message.strip()
            if not message:
                return Text("...", style=waiting_style)
            text = Text("...", style=waiting_style)
            text.append(" ")
            text.append(
                f"[{message}]",
                style=waiting_style,
            )
            return text
        if self._state.kind == ViewStatusKind.ERROR:
            message = self._state.message.strip()
            if message:
                return f"[{self._theme.color_text_error}]{message}[/]"
            return f"[{self._theme.color_text_error}]Error[/]"
        return ""
