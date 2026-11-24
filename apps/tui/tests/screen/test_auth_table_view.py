from __future__ import annotations

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from stui.di.strings import TuiStrings
from stui.screen.auth_table_view import (
    AuthTableProviderRow,
    AuthTableView,
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


@pytest.mark.parametrize("marker", ["✓", "ok"])
def test_auth_table_view_renders_columns_and_configuration(marker: str) -> None:
    class AuthApp(App):
        def compose(self) -> ComposeResult:
            view = AuthTableView(strings=TuiStrings(models_table_provider_configured_marker=marker))
            view.set_rows(
                [
                    AuthTableProviderRow(name="moonshot", adapter="openai", source="user"),
                    AuthTableProviderRow(name="codex", adapter="codex", source="none"),
                ]
            )
            yield view

    async def run() -> None:
        app = AuthApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            assert table.show_header is True
            assert [str(column.label) for column in table.columns.values()] == [
                "Provider",
                "Adapter",
                "Configured",
            ]
            assert table.get_row("moonshot") == ["moonshot", "openai", marker]
            assert table.get_row("codex") == ["codex", "codex", ""]
            assert table.size.height >= 3
            view = app.query_one(AuthTableView)
            assert view.move_selection(1) is True
            assert table.cursor_row == 1
            assert view.selected_provider.name == "codex"

    asyncio.run(run())


def test_auth_table_view_renders_empty_state() -> None:
    class AuthApp(App):
        def compose(self) -> ComposeResult:
            yield AuthTableView()

    async def run() -> None:
        app = AuthApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            assert table.get_row_at(0) == ["No auth providers available.", "", ""]
            assert app.query_one(AuthTableView).selected_provider is None

    asyncio.run(run())
