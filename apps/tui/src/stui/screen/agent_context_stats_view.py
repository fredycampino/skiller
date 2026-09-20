from __future__ import annotations

from dataclasses import replace
from math import ceil

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import AgentContextStatsState

DEFAULT_BAR_WIDTH = 24
MIN_BAR_WIDTH = 8
MAX_BAR_WIDTH = 24
RANGE_BOUNDARY = "▪"
RANGE_EMPTY = "─"
RANGE_FILLED = "━"
RANGE_START_MARKER = "▾"


class AgentContextStatsView(Vertical):
    def __init__(
        self,
        *,
        state: AgentContextStatsState | None = None,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        strings: TuiStrings = DEFAULT_TUI_STRINGS,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._state = replace(state) if state is not None else None
        self._theme = theme
        self._strings = strings
        self._rendered_snapshot: tuple[AgentContextStatsState | None, int] | None = None
        self.display = state is not None

    def compose(self) -> ComposeResult:
        yield Static("", id="agent-context-stats-content")

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh)

    def set_state(self, state: AgentContextStatsState | None) -> None:
        if state == self._state:
            return
        self._state = replace(state) if state is not None else None
        visible = state is not None
        if self.display != visible:
            self.display = visible
        self._refresh()

    def on_resize(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if not self.is_mounted:
            return
        content = self.query_one("#agent-context-stats-content", Static)
        bar_width = content.size.width or DEFAULT_BAR_WIDTH
        snapshot = (self._state, bar_width if self._state is not None else 0)
        if snapshot == self._rendered_snapshot:
            return
        if self._state is None:
            content.update("")
            self._rendered_snapshot = snapshot
            return
        _ = self._strings
        rendered = _render_context_stats(
            self._state,
            theme=self._theme,
            bar_width=bar_width,
        )
        content.update(rendered)
        self._rendered_snapshot = snapshot


def _render_context_stats(
    state: AgentContextStatsState,
    *,
    theme: TuiTheme,
    bar_width: int,
) -> Text:
    width = _bar_width(bar_width)
    start_index = _start_marker_index(state, bar_width=width)
    label_line = _label_line(state, bar_width=width, start_index=start_index)
    text = Text(label_line, style=theme.color_text_muted)
    text.append("\n")
    _append_range_bar(text, state, theme=theme, bar_width=width, start_index=start_index)
    return text


def _append_range_bar(
    text: Text,
    state: AgentContextStatsState,
    *,
    theme: TuiTheme,
    bar_width: int,
    start_index: int,
) -> None:
    width = _bar_width(bar_width)
    end_index = width - 1
    for index in range(width):
        if index == 0 or index == end_index:
            text.append(RANGE_BOUNDARY, style=theme.color_text_muted)
            continue
        if index == start_index:
            text.append(RANGE_START_MARKER, style=theme.color_text_muted)
            continue
        if index > start_index:
            text.append(RANGE_FILLED, style=theme.color_text_muted)
            continue
        text.append(RANGE_EMPTY, style=theme.color_text_muted)


def _label_line(
    state: AgentContextStatsState,
    *,
    bar_width: int,
    start_index: int,
) -> str:
    _ = bar_width, start_index
    return f"{max(state.start_sequence, 0)}-{max(state.end_sequence, 0)}"


def _bar_width(bar_width: int) -> int:
    return min(MAX_BAR_WIDTH, max(MIN_BAR_WIDTH, bar_width))


def _start_marker_index(state: AgentContextStatsState, *, bar_width: int) -> int:
    width = _bar_width(bar_width)
    end_sequence = max(state.end_sequence, 1)
    start_sequence = max(state.start_sequence, 1)
    interior_width = max(width - 2, 1)
    marker_position = ceil((start_sequence / end_sequence) * interior_width)
    return min(width - 2, max(1, marker_position))
