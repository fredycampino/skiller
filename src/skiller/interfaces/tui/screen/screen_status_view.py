from __future__ import annotations

from rich.text import Text
from textual.timer import Timer
from textual.widgets import Static

from skiller.interfaces.tui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from skiller.interfaces.tui.viewmodel.console_screen_state import (
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
        self._state = state or ViewStatusState()
        self._waiting_prompt = ""
        self._theme = theme
        self._frame_index = 0
        self._timer: Timer | None = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(
            self._theme.status_animation_interval,
            self._tick,
            pause=True,
        )
        self._sync_timer()
        self.update(self.render())

    def set_state(
        self,
        state: ViewStatusState,
        *,
        waiting_prompt: str = "",
    ) -> None:
        self._state = state
        self._waiting_prompt = waiting_prompt
        self._sync_timer()
        self.update(self.render())

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
            waiting_style = f"{self._theme.rich_style(self._theme.color_text_secondary)} dim"
            if not self._waiting_prompt:
                return Text("...", style=waiting_style)
            text = Text("...", style=waiting_style)
            text.append(" ")
            text.append(
                f"[{self._waiting_prompt}]",
                style=waiting_style,
            )
            return text
        if self._state.kind == ViewStatusKind.ERROR:
            message = self._state.message.strip()
            if message:
                return f"[{self._theme.color_text_error}]{message}[/]"
            return f"[{self._theme.color_text_error}]Error[/]"
        return ""
