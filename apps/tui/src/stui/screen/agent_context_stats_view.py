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
TURNS_FILLED = "■"
TURNS_EMPTY = "□"
TOKEN_FILLED = "━"
TOKEN_EMPTY = "─"
TOKEN_CURRENT_MARKER = "┴"
TOKEN_LIMIT_MARKER = "▾"


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
        bar_width = content.size.width or DEFAULT_BAR_WIDTH
        rendered = _render_context_stats(
            self._state,
            theme=self._theme,
            strings=self._strings,
            bar_width=bar_width,
        )
        content.update(rendered)


def _render_context_stats(
    state: AgentContextStatsState,
    *,
    theme: TuiTheme,
    strings: TuiStrings,
    bar_width: int,
) -> Text:
    text = Text(strings.agent_context_stats_title, style=theme.color_text_primary)
    text.append("\n\n")
    text.append(
        f"truncate {_truncated_turns(state)}/{_total_turns(state)}",
        style=theme.color_text_secondary,
    )
    text.append("\n")
    _append_turns_bar(text, state, theme=theme, bar_width=bar_width)
    text.append("\n\n")
    token_header = _token_header(state, bar_width=bar_width)
    text.append(token_header, style=theme.color_text_secondary)
    text.append("\n")
    _append_token_bar(text, state, theme=theme, bar_width=bar_width)
    text.append("\n")
    token_limit_marker = _token_limit_marker(state, bar_width=bar_width)
    text.append(token_limit_marker, style=theme.color_text_muted)
    return text


def _append_turns_bar(
    text: Text,
    state: AgentContextStatsState,
    *,
    theme: TuiTheme,
    bar_width: int,
) -> None:
    width = max(bar_width, 1)
    total = max(_total_turns(state), 1)
    truncated = _truncated_turns(state)
    truncated_width = min(width, int((truncated / total) * width))
    text.append(TURNS_EMPTY * truncated_width, style=theme.color_text_muted)
    text.append(TURNS_FILLED * (width - truncated_width), style=theme.color_text_secondary)


def _append_token_bar(
    text: Text,
    state: AgentContextStatsState,
    *,
    theme: TuiTheme,
    bar_width: int,
) -> None:
    width = max(bar_width, 1)
    current_marker_index = _token_current_marker_index(state, bar_width=bar_width)
    limit_marker_index = _token_limit_marker_index(state, bar_width=bar_width)
    token_style = _token_style(state, theme=theme)
    for index in range(width):
        if index == limit_marker_index:
            text.append(TOKEN_LIMIT_MARKER, style=theme.color_text_secondary)
            continue
        if index == current_marker_index:
            text.append(TOKEN_CURRENT_MARKER, style=token_style)
            continue
        if index < current_marker_index:
            text.append(TOKEN_FILLED, style=token_style)
            continue
        text.append(TOKEN_EMPTY, style=theme.color_text_muted)


def _token_header(state: AgentContextStatsState, *, bar_width: int) -> str:
    current = _format_tokens(state.current_tokens)
    capacity = _format_limit_tokens(state.capacity_tokens)
    gap = max(1, bar_width - len(current) - len(capacity))
    return f"{current}{' ' * gap}{capacity}"


def _token_limit_marker(state: AgentContextStatsState, *, bar_width: int) -> str:
    label = f"limit {_format_limit_tokens(state.limit_tokens)}"
    marker_index = _token_limit_marker_index(state, bar_width=bar_width)
    prefix_width = max(0, marker_index - len("limit "))
    return f"{' ' * prefix_width}{label}"


def _token_limit_marker_index(state: AgentContextStatsState, *, bar_width: int) -> int:
    width = max(bar_width, 1)
    capacity = max(state.capacity_tokens, 1)
    limit = max(state.limit_tokens, 0)
    marker_position = ceil((limit / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _token_current_marker_index(state: AgentContextStatsState, *, bar_width: int) -> int:
    width = max(bar_width, 1)
    capacity = max(state.capacity_tokens, 1)
    current = max(state.current_tokens, 0)
    marker_position = ceil((current / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _truncated_turns(state: AgentContextStatsState) -> int:
    return max(state.start_sequence - 1, 0)


def _total_turns(state: AgentContextStatsState) -> int:
    return state.entries + _truncated_turns(state)


def _token_percent(state: AgentContextStatsState) -> int:
    limit = max(state.limit_tokens, 1)
    current = max(state.current_tokens, 0)
    return min(999, round((current / limit) * 100))


def _token_style(state: AgentContextStatsState, *, theme: TuiTheme) -> str:
    percent = _token_percent(state)
    if percent >= 90:
        return theme.color_text_error
    if percent >= 70:
        return theme.color_text_warning
    return theme.color_text_secondary


def _format_tokens(value: int) -> str:
    if value < 1000:
        return str(value)
    if value % 1000 == 0:
        return f"{value // 1000}k"
    return f"{value / 1000:.1f}k"


def _format_limit_tokens(value: int) -> str:
    return _format_tokens(value).replace("k", "K")
