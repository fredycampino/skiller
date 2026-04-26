from __future__ import annotations

from textual.timer import Timer
from textual.widgets import Static

from skiller.interfaces.tui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from skiller.interfaces.tui.viewmodel.console_screen_state import ScreenStatus


class ScreenStatusView(Static):
    def __init__(
        self,
        *,
        status: ScreenStatus = ScreenStatus.READY,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._status = status
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

    def set_status(self, status: ScreenStatus) -> None:
        self._status = status
        self._sync_timer()
        self.update(self.render())

    def _tick(self) -> None:
        self._frame_index = (self._frame_index + 1) % len(self._theme.status_spinner_frames)
        self.update(self.render())

    def _sync_timer(self) -> None:
        if self._timer is None:
            return
        if self._status == ScreenStatus.RUNNING:
            self._timer.resume()
            return
        self._timer.pause()

    def render(self) -> str:
        if self._status == ScreenStatus.RUNNING:
            frame = self._theme.status_spinner_frames[self._frame_index]
            return f"{frame} Running"
        if self._status == ScreenStatus.WAITING:
            return "Waiting"
        if self._status == ScreenStatus.ERROR:
            return f"[{self._theme.color_text_error}]Error[/]"
        return "Ready"
