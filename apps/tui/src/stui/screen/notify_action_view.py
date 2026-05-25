from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import NotifyActionState


class NotifyActionView(Vertical):
    class OpenLink(Message):
        def __init__(self, *, state: NotifyActionState) -> None:
            super().__init__()
            self.state = state

    class Done(Message):
        def __init__(self, *, state: NotifyActionState) -> None:
            super().__init__()
            self.state = state

    def __init__(
        self,
        *,
        state: NotifyActionState | None = None,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        strings: TuiStrings = DEFAULT_TUI_STRINGS,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._state = state
        self._theme = theme
        self._strings = strings
        self._opened = False
        self.display = state is not None

    def compose(self) -> ComposeResult:
        yield Static("", id="notify-action-message")
        yield Horizontal(
            Button(
                self._strings.notify_action_done_label,
                id="notify-action-done",
                compact=True,
            ),
            Static("", id="notify-action-button-spacer"),
            Button(
                "open link",
                id="notify-action-open-link",
                compact=True,
            ),
            id="notify-action-open-link-row",
        )

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh)

    def set_state(self, state: NotifyActionState | None) -> None:
        if state != self._state:
            self._opened = False
        self._state = state
        self.display = state is not None
        self._refresh()

    @on(Button.Pressed, "#notify-action-open-link")
    def _on_open_link_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._state is None:
            return
        self._activate_open_link()

    @on(Button.Pressed, "#notify-action-done")
    def _on_done_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._state is None:
            return
        self.post_message(self.Done(state=self._state))

    def _activate_open_link(self) -> None:
        if self._state is None:
            return
        self._opened = True
        self._refresh()
        self.post_message(self.OpenLink(state=self._state))

    def _refresh(self) -> None:
        if not self.is_mounted:
            return
        message = self.query_one("#notify-action-message", Static)
        done = self.query_one("#notify-action-done", Button)
        open_link = self.query_one("#notify-action-open-link", Button)
        if self._state is None:
            message.update("")
            done.label = self._strings.notify_action_done_label
            done.display = False
            open_link.label = "open link"
            open_link.remove_class("opened")
            open_link.display = False
            return
        message.update(Text(self._state.message, style=self._theme.color_text_primary))
        done.label = self._strings.notify_action_done_label
        done.display = True
        open_link.label = self._state.label
        open_link.set_class(self._opened, "opened")
        open_link.display = True
