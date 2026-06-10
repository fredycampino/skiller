from __future__ import annotations

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
        self._state = state
        self._theme = theme
        self._strings = strings
        self.display = state is not None

    def compose(self) -> ComposeResult:
        yield Static("", id="agent-context-stats-content")

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh)

    def set_state(self, state: AgentContextStatsState | None) -> None:
        self._state = state
        self.display = state is not None
        self._refresh()

    def on_resize(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if not self.is_mounted:
            return
        content = self.query_one("#agent-context-stats-content", Static)
        if self._state is None:
            content.update("")
            return
        _ = self._strings
        bar_width = content.size.width or DEFAULT_BAR_WIDTH
        rendered = _render_context_stats(
            self._state,
            theme=self._theme,
            bar_width=bar_width,
        )
        content.update(rendered)


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
    width = _bar_width(bar_width)
    start_label = str(max(state.start_sequence, 0))
    end_label = str(max(state.end_sequence, 0))
    line = [" "] * width
    _place_label(line, label=start_label, center_index=start_index)
    _place_label(line, label=end_label, center_index=width - 1)
    return "".join(line).rstrip()


def _bar_width(bar_width: int) -> int:
    return min(MAX_BAR_WIDTH, max(MIN_BAR_WIDTH, bar_width))


def _place_label(line: list[str], *, label: str, center_index: int) -> None:
    if not line or not label:
        return
    start = center_index - (len(label) // 2)
    start = min(max(start, 0), max(0, len(line) - len(label)))
    for offset, character in enumerate(label):
        line[start + offset] = character


def _start_marker_index(state: AgentContextStatsState, *, bar_width: int) -> int:
    width = _bar_width(bar_width)
    end_sequence = max(state.end_sequence, 1)
    start_sequence = max(state.start_sequence, 1)
    interior_width = max(width - 2, 1)
    marker_position = ceil((start_sequence / end_sequence) * interior_width)
    return min(width - 2, max(1, marker_position))
