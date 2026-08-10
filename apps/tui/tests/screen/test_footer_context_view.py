from __future__ import annotations

import pytest

from stui.screen.footer_context_view import _render_footer_context, _token_style
from stui.screen.theme import DEFAULT_TUI_THEME
from stui.viewmodel.console_screen_state import (
    AgentMetricsState,
    AgentStepContext,
    AgentStepUsage,
)

pytestmark = pytest.mark.unit


def test_render_footer_context_shows_model_tokens_capacity_and_bar() -> None:
    rendered = _render_footer_context(
        metrics=_metrics(
            current_tokens=59500,
            limit_tokens=80000,
            capacity_tokens=100000,
            cached_tokens=42000,
        ),
        fallback_text="/ for commands",
        theme=DEFAULT_TUI_THEME,
        bar_width=30,
    )

    plain = rendered.plain
    assert plain.startswith("gpt-5.5\n59.5k")
    assert "100K" in plain
    assert "┴" not in plain
    assert "▾" in plain
    assert plain.splitlines()[2] == "╍╍╍╍╍╍╍╍╍╍╍╍╍━━━━━─────▾──────"


def test_render_footer_context_keeps_one_visible_non_cached_token() -> None:
    rendered = _render_footer_context(
        metrics=_metrics(
            current_tokens=100000,
            limit_tokens=80000,
            capacity_tokens=100000,
            cached_tokens=99999,
        ),
        fallback_text="/ for commands",
        theme=DEFAULT_TUI_THEME,
        bar_width=30,
    )

    bar = rendered.plain.splitlines()[2]
    assert "━" in bar
    assert bar.count("╍") == 22



def test_render_footer_context_keeps_limit_marker_fixed_when_usage_overflows() -> None:
    rendered = _render_footer_context(
        metrics=_metrics(
            current_tokens=85000,
            limit_tokens=80000,
            capacity_tokens=100000,
            cached_tokens=0,
        ),
        fallback_text="/ for commands",
        theme=DEFAULT_TUI_THEME,
        bar_width=30,
    )

    bar = rendered.plain.splitlines()[2]
    assert bar[23] == "▾"
    assert bar[24:] == "──────"
    assert bar[:23] == "━━━━━━━━━━━━━━━━━━━━━━━"



def test_token_style_uses_limit_as_warning_threshold() -> None:
    style = _token_style(
        current_tokens=80000,
        limit_tokens=80000,
        capacity_tokens=100000,
        theme=DEFAULT_TUI_THEME,
    )

    assert style == DEFAULT_TUI_THEME.color_text_warning


def test_token_style_uses_ninety_percent_capacity_as_error_threshold() -> None:
    style = _token_style(
        current_tokens=90000,
        limit_tokens=80000,
        capacity_tokens=100000,
        theme=DEFAULT_TUI_THEME,
    )

    assert style == DEFAULT_TUI_THEME.color_text_error


def test_token_style_is_secondary_below_limit() -> None:
    style = _token_style(
        current_tokens=79999,
        limit_tokens=80000,
        capacity_tokens=100000,
        theme=DEFAULT_TUI_THEME,
    )

    assert style == DEFAULT_TUI_THEME.color_text_secondary


def test_render_footer_context_uses_fallback_without_context() -> None:
    rendered = _render_footer_context(
        metrics=None,
        fallback_text="gpt-5.5\n59.5k",
        theme=DEFAULT_TUI_THEME,
        bar_width=30,
    )

    assert rendered.plain == "gpt-5.5\n59.5k"


def _metrics(
    *,
    current_tokens: int,
    limit_tokens: int,
    capacity_tokens: int,
    cached_tokens: int,
) -> AgentMetricsState:
    return AgentMetricsState(
        usage=AgentStepUsage(
            prompt_tokens=current_tokens,
            output_tokens=None,
            total_tokens=None,
            cache_read_tokens=cached_tokens,
            cache_write_tokens=None,
            provider=None,
            model="gpt-5.5",
        ),
        context=AgentStepContext(
            effective_window_tokens=capacity_tokens,
            max_total_tokens_ratio=limit_tokens / capacity_tokens,
        ),
    )
