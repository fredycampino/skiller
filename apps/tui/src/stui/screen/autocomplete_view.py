from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
)


class AutoCompleteView(Static):
    def __init__(
        self,
        *,
        visible: bool = False,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._theme = theme
        self._state: CompletionState | None = None
        self.display = visible

    def on_mount(self) -> None:
        self._refresh()

    def set_state(
        self,
        state: CompletionState | None,
        *,
        reserve_space: bool = False,
    ) -> None:
        self._state = state
        active = self.is_visible()
        self.display = active or reserve_space
        self.styles.visibility = "visible" if active else "hidden"
        self._refresh()

    def is_visible(self) -> bool:
        return bool(self._state and self._state.visible and self._state.items)

    @property
    def selected_item(self) -> CompletionItem | None:
        if self._state is None:
            return None
        return self._state.selected_item

    def render(self) -> Text:
        if self._state is None or not self._state.visible or not self._state.items:
            return Text("")

        label_width = max(len(item.label) for item in self._state.items) + 2
        muted_style = self._theme.color_text_secondary
        selected_style = self._theme.color_text_accent
        description_style = self._theme.color_text_secondary

        renderable = Text()
        for index, item in enumerate(self._state.items):
            if index > 0:
                renderable.append("\n")

            is_selected = index == self._state.selected_index
            prefix = f"{self._theme.autocomplete_selector_icon} " if is_selected else "   "
            line_style = selected_style if is_selected else muted_style

            line = Text(
                f"{prefix}{item.label.ljust(label_width)}",
                style=line_style,
            )
            if item.description:
                line.append(
                    item.description,
                    style=description_style if not is_selected else line_style,
                )
            renderable.append(line)
        return renderable

    def _refresh(self) -> None:
        if not self.is_mounted:
            return
        self.update(self.render())
