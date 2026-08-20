from __future__ import annotations

import pytest

from stui.di.strings import TuiStrings
from stui.screen.auth_table_view import (
    AuthTableProviderRow,
    AuthTableView,
    format_provider_label,
)

pytestmark = pytest.mark.unit


def test_auth_table_view_tracks_provider_selection() -> None:
    view = AuthTableView()
    view.set_rows(
        [
            AuthTableProviderRow(name="moonshot", adapter="openai", source="user"),
            AuthTableProviderRow(name="codex", adapter="codex", source="none"),
        ]
    )

    assert view.selected_provider is not None
    assert view.selected_provider.name == "moonshot"
    assert view.selected_provider.adapter == "openai"
    assert view.move_selection(1) is True
    assert view.selected_provider is not None
    assert view.selected_provider.name == "codex"


def test_auth_table_view_marks_configured_provider() -> None:
    view = AuthTableView()
    view.set_rows(
        [
            AuthTableProviderRow(name="moonshot", adapter="openai", source="user"),
            AuthTableProviderRow(name="codex", adapter="codex", source="none"),
        ]
    )

    assert view.render_providers_text().splitlines() == [
        "moonshot · openai ✓",
        "codex · codex",
    ]
    assert format_provider_label(
        AuthTableProviderRow(name="moonshot", adapter="openai", source="user"),
        TuiStrings(models_table_provider_configured_marker="ok"),
    ) == "moonshot · openai ok"
