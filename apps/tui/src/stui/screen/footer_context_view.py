from __future__ import annotations

from math import ceil

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import FooterContextState

DEFAULT_BAR_WIDTH = 24
TOKEN_FILLED = "━"
TOKEN_EMPTY = "─"
TOKEN_CURRENT_MARKER = "┴"
TOKEN_LIMIT_MARKER = "▾"


class FooterContextView(Static):
    def __init__(
        self,
        *,
        state: FooterContextState | None = None,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        fallback_text: str = "/ for commands",
        max_bar_width: int | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._state = state
        self._theme = theme
        self._fallback_text = fallback_text
        self._max_bar_width = max_bar_width

    def compose(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh)

    def set_state(
        self,
        state: FooterContextState | None,
        *,
        fallback_text: str = "/ for commands",
    ) -> None:
        self._state = state
        self._fallback_text = fallback_text
        self._refresh()

    def on_resize(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if not self.is_mounted:
            return
        bar_width = self.size.width or DEFAULT_BAR_WIDTH
        if self._max_bar_width is not None:
            bar_width = min(bar_width, self._max_bar_width)
        self.update(
            _render_footer_context(
                state=self._state,
                fallback_text=self._fallback_text,
                theme=self._theme,
                bar_width=bar_width,
            )
        )


def _render_footer_context(
    *,
    state: FooterContextState | None,
    fallback_text: str,
    theme: TuiTheme,
    bar_width: int,
) -> Text:
    if state is None:
        return Text(fallback_text, style=theme.color_text_secondary)

    text = Text(state.model, style=theme.color_text_secondary)
    text.append("\n")
    text.append(_token_header(state, bar_width=bar_width), style=theme.color_text_secondary)
    text.append("\n")
    _append_token_bar(text, state, theme=theme, bar_width=bar_width)
    return text


def _append_token_bar(
    text: Text,
    state: FooterContextState,
    *,
    theme: TuiTheme,
    bar_width: int,
) -> None:
    width = max(bar_width, 1)
    current_marker_index = _token_current_marker_index(state, bar_width=bar_width)
    limit_marker_index = _visible_token_limit_marker_index(
        state,
        current_marker_index=current_marker_index,
        bar_width=bar_width,
    )
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


def _token_header(state: FooterContextState, *, bar_width: int) -> str:
    current = _format_tokens(state.current_tokens)
    capacity = _format_limit_tokens(state.capacity_tokens)
    gap = max(1, bar_width - len(current) - len(capacity))
    return f"{current}{' ' * gap}{capacity}"


def _visible_token_limit_marker_index(
    state: FooterContextState,
    *,
    current_marker_index: int,
    bar_width: int,
) -> int:
    width = max(bar_width, 1)
    limit_marker_index = _token_limit_marker_index(state, bar_width=bar_width)
    if width > 1 and limit_marker_index == current_marker_index:
        return min(width - 1, limit_marker_index + 1)
    return limit_marker_index


def _token_limit_marker_index(state: FooterContextState, *, bar_width: int) -> int:
    width = max(bar_width, 1)
    capacity = max(state.capacity_tokens, 1)
    limit = max(state.limit_tokens, 0)
    marker_position = ceil((limit / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _token_current_marker_index(state: FooterContextState, *, bar_width: int) -> int:
    width = max(bar_width, 1)
    capacity = max(state.capacity_tokens, 1)
    current = max(state.current_tokens, 0)
    marker_position = ceil((current / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _token_percent(state: FooterContextState) -> int:
    limit = max(state.limit_tokens, 1)
    current = max(state.current_tokens, 0)
    return min(999, round((current / limit) * 100))


def _token_style(state: FooterContextState, *, theme: TuiTheme) -> str:
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
