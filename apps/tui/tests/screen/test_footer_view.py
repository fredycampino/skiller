from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from stui.screen.footer_view import FooterView

pytestmark = pytest.mark.unit


def test_footer_view_updates_only_when_state_changes() -> None:
    async def run() -> None:
        app = _FooterHarness()
        async with app.run_test(size=(100, 12)) as pilot:
            await pilot.pause()
            view = app.query_one(FooterView)
            session = app.query_one("#footer-wide-session", Static)

            with patch.object(session, "update", wraps=session.update) as update:
                view.set_state(session_key="main", run_name=None, metrics=None)
                update.assert_not_called()

                view.set_state(
                    session_key="run-1",
                    run_name="flows/chat.yaml",
                    metrics=None,
                )
                update.assert_called_once_with("run-1\n/chat.yaml")

    asyncio.run(run())


def test_footer_view_switches_layout_after_resize() -> None:
    async def run() -> None:
        app = _FooterHarness()
        async with app.run_test(size=(100, 12)) as pilot:
            await pilot.pause()
            wide = app.query_one("#footer-wide")
            narrow = app.query_one("#footer-narrow")
            assert wide.display is True
            assert narrow.display is False

            await pilot.resize_terminal(60, 12)
            await pilot.pause()

            assert wide.display is False
            assert narrow.display is True

    asyncio.run(run())


class _FooterHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield FooterView(
            session_key="main",
            run_name=None,
            metrics=None,
            id="footer",
        )
