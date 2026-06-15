from __future__ import annotations

import pytest
from rich.text import Text

from stui.di.strings import TuiStrings
from stui.screen.models_table_view import (
    ModelsTableModelRow,
    ModelsTableProviderRow,
    ModelsTableView,
)
from stui.screen.theme import TuiTheme

pytestmark = pytest.mark.unit


def test_models_table_view_tracks_provider_and_model_selection() -> None:
    view = ModelsTableView()
    view.set_rows(_rows())

    assert view.selected_provider is not None
    assert view.selected_provider.name == "codex"
    assert view.selected_model is not None
    assert view.selected_model.name == "gpt-5.5"

    assert view.move_provider_selection(1) is True
    assert view.selected_provider is not None
    assert view.selected_provider.name == "minimax"
    assert view.focus_models() is True
    assert view.move_model_selection(1) is True
    assert view.selected_model is not None
    assert view.selected_model.name == "MiniMax-M2.5"


def test_models_table_view_blocks_model_focus_for_unconfigured_provider() -> None:
    view = ModelsTableView()
    view.set_rows(_rows())

    assert view.move_provider_selection(2) is True
    assert view.selected_provider is not None
    assert view.selected_provider.name == "bedrock"
    assert view.focus_models() is False
    assert view.selected_model is None


def test_models_table_view_keeps_model_selection_by_provider() -> None:
    view = ModelsTableView()
    view.set_rows(_rows())

    assert view.focus_models() is True
    assert view.move_model_selection(1) is True
    assert view.selected_model is not None
    assert view.selected_model.name == "gpt-5.4"

    assert view.focus_providers() is True
    assert view.move_provider_selection(1) is True
    assert view.focus_models() is True
    assert view.move_model_selection(1) is True
    assert view.selected_model is not None
    assert view.selected_model.name == "MiniMax-M2.5"

    assert view.focus_providers() is True
    assert view.move_provider_selection(-1) is True
    assert view.selected_model is None
    assert view.focus_models() is True
    assert view.selected_model is not None
    assert view.selected_model.name == "gpt-5.4"


def test_models_table_view_does_not_select_inactive_model_while_provider_focused() -> None:
    view = ModelsTableView()
    view.set_rows(_rows())

    assert view.move_provider_selection(1) is True
    assert view.selected_provider is not None
    assert view.selected_provider.name == "minimax"
    assert view.selected_model is None

    assert view.focus_models() is True
    assert view.selected_model is not None
    assert view.selected_model.name == "MiniMax-M2.7"


def test_models_table_view_uses_active_model_as_default_selection() -> None:
    view = ModelsTableView()
    view.set_rows([
        ModelsTableProviderRow(
            name="codex",
            source="global",
            models=(ModelsTableModelRow(name="gpt-5.4"),),
        ),
        ModelsTableProviderRow(
            name="minimax",
            source="global",
            models=(
                ModelsTableModelRow(name="MiniMax-M2.7"),
                ModelsTableModelRow(name="MiniMax-M2.5", active=True),
            ),
        ),
    ])

    assert view.selected_provider is not None
    assert view.selected_provider.name == "minimax"
    assert view.selected_model is not None
    assert view.selected_model.name == "MiniMax-M2.5"


def test_models_table_view_renders_provider_and_models_panel() -> None:
    view = ModelsTableView()
    view.set_rows(_rows())

    providers = view.render_providers_text()
    models = view.render_models_text()

    assert "codex ✓" in providers
    assert models.splitlines()[0] == "● gpt-5.5"
    assert "┌" not in models


def test_models_table_view_uses_configured_strings() -> None:
    view = ModelsTableView(
        strings=TuiStrings(
            models_table_provider_configured_marker="ok",
            models_table_active_model_marker="active",
        )
    )
    view.set_rows(_rows())

    assert "codex ok" in view.render_providers_text()
    assert view.render_models_text().splitlines()[0] == "active gpt-5.5"


def test_models_table_view_orders_configured_providers_first() -> None:
    view = ModelsTableView()
    view.set_rows([
        ModelsTableProviderRow(name="bedrock", source="none", models=()),
        ModelsTableProviderRow(name="codex", source="global", models=()),
        ModelsTableProviderRow(name="minimax", source="global", models=()),
    ])

    assert view.render_providers_text().splitlines() == ["codex ✓", "minimax ✓", "bedrock"]


def test_models_table_view_warns_when_selected_provider_needs_auth() -> None:
    view = ModelsTableView(
        theme=TuiTheme(color_text_warning="warning"),
    )
    view.set_rows(_rows())

    assert view.move_provider_selection(2) is True
    content = view.render_status_content()

    assert isinstance(content, Text)
    assert content.plain == "Run /auth bedrock to configure"
    assert content.style == "warning"


def test_models_table_view_does_not_warn_for_global_provider() -> None:
    view = ModelsTableView(
        theme=TuiTheme(color_text_warning="warning"),
    )
    view.set_rows([
        ModelsTableProviderRow(
            name="minimax",
            source="global",
            models=(ModelsTableModelRow(name="MiniMax-M2.7"),),
        )
    ])

    content = view.render_status_content()

    assert content == "Select a model"


def _rows() -> list[ModelsTableProviderRow]:
    return [
        ModelsTableProviderRow(
            name="codex",
            source="global",
            models=(
                ModelsTableModelRow(name="gpt-5.5", active=True),
                ModelsTableModelRow(name="gpt-5.4"),
            ),
        ),
        ModelsTableProviderRow(
            name="minimax",
            source="global",
            models=(
                ModelsTableModelRow(name="MiniMax-M2.7"),
                ModelsTableModelRow(name="MiniMax-M2.5"),
            ),
        ),
        ModelsTableProviderRow(
            name="bedrock",
            source="none",
            models=(ModelsTableModelRow(name="us.anthropic.claude-sonnet-4-6"),),
        ),
    ]
