from __future__ import annotations

from math import ceil

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import AgentMetricsState

DEFAULT_BAR_WIDTH = 24


class FooterContextView(Static):
    def __init__(
        self,
        *,
        metrics: AgentMetricsState | None,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        fallback_text: str = "/ for commands",
        max_bar_width: int | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._metrics = metrics
        self._theme = theme
        self._fallback_text = fallback_text
        self._max_bar_width = max_bar_width

    def compose(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh)

    def set_state(
        self,
        *,
        metrics: AgentMetricsState | None,
        fallback_text: str = "/ for commands",
    ) -> None:
        self._metrics = metrics
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
                metrics=self._metrics,
                fallback_text=_build_footer_usage_text(
                    metrics=self._metrics,
                    fallback_text=self._fallback_text,
                ),
                theme=self._theme,
                bar_width=bar_width,
            )
        )


def _render_footer_context(
    *,
    metrics: AgentMetricsState | None,
    fallback_text: str,
    theme: TuiTheme,
    bar_width: int,
) -> Text:
    if metrics is None or metrics.usage is None or metrics.context is None:
        return Text(fallback_text, style=theme.color_text_secondary)
    usage = metrics.usage
    context = metrics.context
    if (
        usage.model is None
        or usage.prompt_tokens is None
        or context.effective_window_tokens is None
        or context.max_total_tokens_ratio is None
    ):
        return Text(fallback_text, style=theme.color_text_secondary)
    current_tokens = usage.prompt_tokens
    estimated_system_tokens = usage.estimated_system_tokens or 0
    capacity_tokens = context.effective_window_tokens
    limit_tokens = int(capacity_tokens * context.max_total_tokens_ratio)
    cached_tokens = usage.cache_read_tokens or 0
    text = Text(usage.model, style=theme.color_text_secondary)
    text.append("\n")
    text.append(
        _token_header(
            current_tokens=current_tokens,
            capacity_tokens=capacity_tokens,
            bar_width=bar_width,
        ),
        style=theme.color_text_secondary,
    )
    text.append("\n")
    _append_token_bar(
        text,
        current_tokens=current_tokens,
        estimated_system_tokens=estimated_system_tokens,
        limit_tokens=limit_tokens,
        capacity_tokens=capacity_tokens,
        cached_tokens=cached_tokens,
        theme=theme,
        bar_width=bar_width,
    )
    return text


def _build_footer_usage_text(
    *,
    metrics: AgentMetricsState | None,
    fallback_text: str,
) -> str:
    if metrics is None or metrics.usage is None:
        return fallback_text
    usage = metrics.usage
    if usage.model is None or usage.prompt_tokens is None:
        return fallback_text
    return f"{usage.model}\n{_format_agent_tokens(usage.prompt_tokens)}"


def _format_agent_tokens(value: int) -> str:
    if value < 1000:
        return str(value)
    return f"{value / 1000:.1f}k"


def _append_token_bar(
    text: Text,
    *,
    current_tokens: int,
    estimated_system_tokens: int,
    limit_tokens: int,
    capacity_tokens: int,
    cached_tokens: int,
    theme: TuiTheme,
    bar_width: int,
) -> None:
    width = max(bar_width, 1)
    current_marker_index = _token_current_marker_index(
        current_tokens=current_tokens,
        capacity_tokens=capacity_tokens,
        bar_width=bar_width,
    )
    limit_marker_index = _token_limit_marker_index(
        limit_tokens=limit_tokens,
        capacity_tokens=capacity_tokens,
        bar_width=bar_width,
    )
    occupied_marker_index = min(current_marker_index, limit_marker_index - 1)
    system_marker_index = -1
    if estimated_system_tokens > 0:
        system_marker_index = min(
            _token_current_marker_index(
                current_tokens=estimated_system_tokens,
                capacity_tokens=capacity_tokens,
                bar_width=bar_width,
            ),
            occupied_marker_index,
        )
    cached_marker_index = min(
        _token_cached_marker_index(
            current_tokens=current_tokens,
            cached_tokens=cached_tokens,
            capacity_tokens=capacity_tokens,
            bar_width=bar_width,
        ),
        occupied_marker_index,
    )
    non_cached_marker_index = _token_non_cached_marker_index(
        current_tokens=current_tokens,
        cached_tokens=cached_tokens,
        current_marker_index=occupied_marker_index,
        cached_marker_index=cached_marker_index,
    )
    system_style = _token_style(
        current_tokens=current_tokens,
        limit_tokens=limit_tokens,
        capacity_tokens=capacity_tokens,
        theme=theme,
    )
    for index in range(width):
        if index == limit_marker_index:
            text.append(theme.footer_bar.limit_marker, style=theme.color_text_secondary)
            continue
        if index <= occupied_marker_index:
            if index <= system_marker_index:
                text.append(theme.footer_bar.filled_token, style=system_style)
                continue
            if index <= cached_marker_index and index != non_cached_marker_index:
                text.append(theme.footer_bar.cached_token, style=theme.color_text_muted)
                continue
            text.append(theme.footer_bar.filled_token, style=theme.color_text_primary)
            continue
        text.append(theme.footer_bar.empty_token, style=theme.color_text_muted)


def _token_header(*, current_tokens: int, capacity_tokens: int, bar_width: int) -> str:
    current = _format_tokens(current_tokens)
    capacity = _format_limit_tokens(capacity_tokens)
    gap = max(1, bar_width - len(current) - len(capacity))
    return f"{current}{' ' * gap}{capacity}"


def _token_limit_marker_index(
    *,
    limit_tokens: int,
    capacity_tokens: int,
    bar_width: int,
) -> int:
    width = max(bar_width, 1)
    capacity = max(capacity_tokens, 1)
    limit = max(limit_tokens, 0)
    marker_position = ceil((limit / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _token_current_marker_index(
    *,
    current_tokens: int,
    capacity_tokens: int,
    bar_width: int,
) -> int:
    width = max(bar_width, 1)
    capacity = max(capacity_tokens, 1)
    current = max(current_tokens, 0)
    marker_position = ceil((current / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _token_cached_marker_index(
    *,
    current_tokens: int,
    cached_tokens: int,
    capacity_tokens: int,
    bar_width: int,
) -> int:
    width = max(bar_width, 1)
    capacity = max(capacity_tokens, 1)
    current = max(current_tokens, 0)
    cached = min(max(cached_tokens, 0), current)
    if current == 0 or cached == 0:
        return -1
    marker_position = ceil((cached / capacity) * width) - 1
    return min(width - 1, max(0, marker_position))


def _token_non_cached_marker_index(
    *,
    current_tokens: int,
    cached_tokens: int,
    current_marker_index: int,
    cached_marker_index: int,
) -> int:
    current = max(current_tokens, 0)
    cached = min(max(cached_tokens, 0), current)
    if cached >= current or current_marker_index < 0:
        return -1
    if cached_marker_index >= current_marker_index:
        return current_marker_index
    return cached_marker_index + 1


def _token_style(
    *,
    current_tokens: int,
    limit_tokens: int,
    capacity_tokens: int,
    theme: TuiTheme,
) -> str:
    current = max(current_tokens, 0)
    capacity = max(capacity_tokens, 1)
    limit = max(limit_tokens, 0)
    if current * 10 >= capacity * 9:
        return theme.color_text_error
    if current >= limit:
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
