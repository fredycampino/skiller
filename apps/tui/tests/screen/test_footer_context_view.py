from __future__ import annotations

import pytest

from stui.screen.footer_context_view import _render_footer_context, _token_style
from stui.screen.theme import DEFAULT_TUI_THEME
from stui.viewmodel.console_screen_state import FooterContextState

pytestmark = pytest.mark.unit


def test_render_footer_context_shows_model_tokens_capacity_and_bar() -> None:
    rendered = _render_footer_context(
        state=FooterContextState(
            model="gpt-5.5",
            current_tokens=59500,
            limit_tokens=80000,
            capacity_tokens=100000,
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
    assert plain.splitlines()[2] == "━━━━━━━━━━━━━━━━━━─────▾──────"


def test_token_style_uses_limit_as_warning_threshold() -> None:
    style = _token_style(
        FooterContextState(
            model="gpt-5.5",
            current_tokens=80000,
            limit_tokens=80000,
            capacity_tokens=100000,
        ),
        theme=DEFAULT_TUI_THEME,
    )

    assert style == DEFAULT_TUI_THEME.color_text_warning


def test_token_style_uses_ninety_percent_capacity_as_error_threshold() -> None:
    style = _token_style(
        FooterContextState(
            model="gpt-5.5",
            current_tokens=90000,
            limit_tokens=80000,
            capacity_tokens=100000,
        ),
        theme=DEFAULT_TUI_THEME,
    )

    assert style == DEFAULT_TUI_THEME.color_text_error


def test_token_style_is_secondary_below_limit() -> None:
    style = _token_style(
        FooterContextState(
            model="gpt-5.5",
            current_tokens=79999,
            limit_tokens=80000,
            capacity_tokens=100000,
        ),
        theme=DEFAULT_TUI_THEME,
    )

    assert style == DEFAULT_TUI_THEME.color_text_secondary


def test_render_footer_context_uses_fallback_without_context() -> None:
    rendered = _render_footer_context(
        state=None,
        fallback_text="gpt-5.5\n59.5k",
        theme=DEFAULT_TUI_THEME,
        bar_width=30,
    )

    assert rendered.plain == "gpt-5.5\n59.5k"
