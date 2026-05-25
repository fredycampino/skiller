from __future__ import annotations

import asyncio

import pytest
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from stui.di.strings import TuiStrings
from stui.screen.notify_action_view import NotifyActionView
from stui.screen.theme import build_textual_css
from stui.viewmodel.console_screen_state import NotifyActionState

pytestmark = pytest.mark.unit

LONG_NOTIFY_ACTION_MESSAGE = (
    "Authorize the app with the external provider. This message is intentionally "
    "long so the TUI notification can show how action text wraps while keeping "
    "the button aligned on the right side."
)


def test_notify_action_view_renders_empty_without_state() -> None:
    view = NotifyActionView()

    assert view.display is False


def test_notify_action_view_renders_action_details() -> None:
    async def run() -> None:
        app = _NotifyActionHarness(state=_action_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            message = app.query_one("#notify-action-message", Static)
            open_link = app.query_one("#notify-action-open-link", Button)
            done = app.query_one("#notify-action-done", Button)
            view = app.query_one(NotifyActionView)

            assert view.display is True
            assert str(message.content) == LONG_NOTIFY_ACTION_MESSAGE
            assert done.display is True
            assert str(done.label) == "done"
            assert open_link.display is True
            assert str(open_link.label) == "Open authorization"

    asyncio.run(run())


def test_notify_action_view_set_state_toggles_visibility() -> None:
    async def run() -> None:
        app = _NotifyActionHarness(state=None)
        async with app.run_test() as pilot:
            view = app.query_one(NotifyActionView)
            message = app.query_one("#notify-action-message", Static)
            done = app.query_one("#notify-action-done", Button)
            open_link = app.query_one("#notify-action-open-link", Button)

            view.set_state(_action_state())
            await pilot.pause()

            assert view.display is True
            assert str(message.content) == LONG_NOTIFY_ACTION_MESSAGE
            assert done.display is True
            assert str(done.label) == "done"
            assert open_link.display is True
            assert str(open_link.label) == "Open authorization"

            view.set_state(None)
            await pilot.pause()

            assert view.display is False
            assert str(message.content) == ""
            assert done.display is False
            assert open_link.display is False

    asyncio.run(run())


def test_notify_action_view_uses_done_label_from_strings() -> None:
    async def run() -> None:
        app = _NotifyActionHarness(
            state=_action_state(),
            strings=TuiStrings(notify_action_done_label="complete"),
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            done = app.query_one("#notify-action-done", Button)

            assert str(done.label) == "complete"

    asyncio.run(run())


def test_notify_action_view_emits_open_link_from_keyboard() -> None:
    async def run() -> None:
        action_state = _action_state()
        app = _NotifyActionHarness(state=action_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            open_link = app.query_one("#notify-action-open-link", Button)
            open_link.focus()

            await pilot.press("enter")
            await pilot.pause()

            assert str(open_link.label) == "Open authorization"
            assert open_link.has_class("opened")

        assert app.opened == [action_state]

    asyncio.run(run())


def test_notify_action_view_emits_open_link_from_click() -> None:
    async def run() -> None:
        action_state = _action_state()
        app = _NotifyActionHarness(state=action_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            open_link = app.query_one("#notify-action-open-link", Button)

            await pilot.click("#notify-action-open-link")
            await pilot.pause()

            assert str(open_link.label) == "Open authorization"
            assert open_link.has_class("opened")

        assert app.opened == [action_state]

    asyncio.run(run())


def test_notify_action_view_emits_done_from_click() -> None:
    async def run() -> None:
        action_state = _action_state()
        app = _NotifyActionHarness(state=action_state)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.click("#notify-action-done")
            await pilot.pause()

        assert app.done == [action_state]

    asyncio.run(run())


def test_notify_action_view_resets_opened_state_when_action_changes() -> None:
    async def run() -> None:
        app = _NotifyActionHarness(state=_action_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            view = app.query_one(NotifyActionView)
            open_link = app.query_one("#notify-action-open-link", Button)

            await pilot.click("#notify-action-open-link")
            await pilot.pause()

            assert open_link.has_class("opened")

            view.set_state(
                NotifyActionState(
                    run_id="run-2",
                    step_id="other_link",
                    message=LONG_NOTIFY_ACTION_MESSAGE,
                    label="Open other link",
                    url="https://example.com/other",
                    status="pending",
                )
            )
            await pilot.pause()

            assert not open_link.has_class("opened")
            assert str(open_link.label) == "Open other link"

    asyncio.run(run())


def _action_state() -> NotifyActionState:
    return NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message=LONG_NOTIFY_ACTION_MESSAGE,
        label="Open authorization",
        url="https://example.com/oauth/start",
        status="pending",
    )


class _NotifyActionHarness(App[None]):
    CSS = build_textual_css()

    def __init__(
        self,
        *,
        state: NotifyActionState | None,
        strings: TuiStrings | None = None,
    ) -> None:
        super().__init__()
        self.action_state = state
        self.strings = strings or TuiStrings()
        self.opened: list[NotifyActionState] = []
        self.done: list[NotifyActionState] = []

    def compose(self) -> ComposeResult:
        yield NotifyActionView(
            state=self.action_state,
            strings=self.strings,
            id="notify-action",
        )

    @on(NotifyActionView.OpenLink)
    def _on_notify_action_open_link(self, event: NotifyActionView.OpenLink) -> None:
        self.opened.append(event.state)

    @on(NotifyActionView.Done)
    def _on_notify_action_done(self, event: NotifyActionView.Done) -> None:
        self.done.append(event.state)
