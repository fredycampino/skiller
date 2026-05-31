from __future__ import annotations

import pytest
from rich.text import Text

from stui.screen.autocomplete_view import AutoCompleteView
from stui.screen.theme import TuiTheme
from stui.viewmodel.console_screen_state import (
    CompletionItem,
    CompletionState,
)

pytestmark = pytest.mark.unit


def test_autocomplete_view_renders_mock_items() -> None:
    view = AutoCompleteView()
    view.set_state(
        CompletionState(
            visible=True,
            query="/ru",
            items=(
                CompletionItem(label="runs", description="Show runs", insert_text="/runs"),
                CompletionItem(label="run", description="Run an agentic flow", insert_text="/run"),
                CompletionItem(
                    label="quit",
                    description="Exit the TUI",
                    insert_text="/quit",
                ),
            ),
            selected_index=1,
            replace_from=0,
            replace_to=3,
        )
    )

    renderable = view.render()

    assert isinstance(renderable, Text)
    assert (
        renderable.plain
        == "   runs  Show runs\n-> run   Run an agentic flow\n   quit  Exit the TUI"
    )


def test_autocomplete_view_exposes_selected_item_from_state() -> None:
    view = AutoCompleteView()
    state = CompletionState(
        visible=True,
        query="/ru",
        items=(
            CompletionItem(label="runs", description="Show runs", insert_text="/runs"),
            CompletionItem(label="run", description="Run an agentic flow", insert_text="/run"),
            CompletionItem(
                label="quit",
                description="Exit the TUI",
                insert_text="/quit",
            ),
        ),
        selected_index=1,
        replace_from=0,
        replace_to=3,
    )

    view.set_state(state)

    assert view.selected_item is not None
    assert view.selected_item.label == "run"
    assert view.is_visible() is True


def test_autocomplete_view_can_reserve_hidden_layout_space() -> None:
    view = AutoCompleteView()

    view.set_state(None, reserve_space=True)

    assert view.display is True
    assert view.styles.visibility == "hidden"
    assert view.render().plain == ""


def test_autocomplete_view_uses_theme_icon_and_accent_for_selection() -> None:
    theme = TuiTheme(
        autocomplete_selector_icon="⇢",
        color_text_accent="magenta",
        color_text_secondary="grey50",
    )
    view = AutoCompleteView(theme=theme)
    view.set_state(
        CompletionState(
            visible=True,
            query="/ru",
            items=(
                CompletionItem(label="runs", description="Show runs", insert_text="/runs"),
                CompletionItem(label="run", description="Run an agentic flow", insert_text="/run"),
            ),
            selected_index=1,
            replace_from=0,
            replace_to=3,
        )
    )

    renderable = view.render()

    assert isinstance(renderable, Text)
    assert "⇢ run" in renderable.plain
    assert any(span.style == theme.color_text_accent for span in renderable.spans)
