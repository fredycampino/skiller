from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Static, TextArea

from skiller.interfaces.tui.screen.console_screen import ConsoleScreen
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    InfoItem,
    ScreenStatus,
    UserInputItem,
)
from skiller.interfaces.tui.viewmodel.console_screen_viewmodel import ConsoleScreenViewModel

pytestmark = pytest.mark.unit


class NeverCalledRunPort:
    def run(self, raw_args: str):  # noqa: ANN001
        raise AssertionError(f"unexpected run call: {raw_args}")

    def subscribe(self, observer: object) -> None:
        _ = observer

    def unsubscribe(self, observer: object) -> None:
        _ = observer


def test_console_screen_clears_prompt_after_local_submit() -> None:
    async def run() -> None:
        viewmodel = ConsoleScreenViewModel(
            session_key="main",
            run_port=NeverCalledRunPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("h", "o", "l", "a", "enter")
            await pilot.pause()

            prompt = app.query_one("#prompt", TextArea)
            assert prompt.text == ""
            assert app.state.screen_status == ScreenStatus.READY
            assert isinstance(app.state.transcript_items[0], UserInputItem)
            assert isinstance(app.state.transcript_items[1], InfoItem)

    asyncio.run(run())


def test_console_screen_shows_quit_hint_in_footer() -> None:
    async def run() -> None:
        viewmodel = ConsoleScreenViewModel(
            session_key="main",
            run_port=NeverCalledRunPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            footer = app.query_one("#footer", Static)
            assert footer.content == "/quit exit"

    asyncio.run(run())
