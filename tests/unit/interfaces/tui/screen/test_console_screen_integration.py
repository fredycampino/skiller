from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Static, TextArea

import skiller.interfaces.tui.usecase.list_runs_use_case as list_runs_use_case_module
from skiller.interfaces.tui.screen.autocomplete_view import AutoCompleteView
from skiller.interfaces.tui.screen.console_screen import ConsoleScreen
from skiller.interfaces.tui.screen.runs_table_view import RunsTableView
from skiller.interfaces.tui.screen.screen_status_view import ScreenStatusView
from skiller.interfaces.tui.screen.transcript_log import TranscriptLog
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    InfoItem,
    OutputFormat,
    RunOutputItem,
    RunStepItem,
    ScreenStatus,
    UserInputItem,
)
from tests.unit.interfaces.tui.support import (
    ActivatingRunPort,
    FakeRunsPort,
    NeverCalledRunPort,
    NeverCalledWaitingPort,
    build_viewmodel,
    make_runs_port_item,
    patched_to_thread,
)

pytestmark = pytest.mark.unit


def test_console_screen_clears_prompt_after_local_submit() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(
                runs=[make_runs_port_item(run_id="run-1234", wait_type="input")]
            ),
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


def test_console_screen_exits_on_quit_command() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="session-123",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        exited: list[str | None] = []

        def fake_exit(result: str | None = None) -> None:
            exited.append(result)

        app.exit = fake_exit  # type: ignore[method-assign]

        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("/", "q", "u", "i", "t", "enter")
            await pilot.pause()

        assert exited == ["session-123"]

    asyncio.run(run())


def test_console_screen_shows_quit_hint_and_session_id_in_footer() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="f8784230-f23d-4b34-b8d1-fb025bb44787",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            footer_left = app.query_one("#footer-left", Static)
            footer_right = app.query_one("#footer-right", Static)
            assert footer_left.content == "/quit exit"
            assert footer_right.content == "f8784230-f23d-4b34-b8d1-fb025bb44787"

    asyncio.run(run())


def test_console_screen_shows_icon_when_session_is_main() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(
                runs=[make_runs_port_item(run_id="run-1234", wait_type="input")]
            ),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            footer_right = app.query_one("#footer-right", Static)
            assert footer_right.content == "◌"

    asyncio.run(run())


def test_console_screen_closes_runs_table_with_enter_on_selected_row() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(
                runs=[make_runs_port_item(run_id="run-1234", wait_type="input")]
            ),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            status = app.query_one("#status", ScreenStatusView)
            runs_table_area = app.query_one("#runs-table-area")
            runs_table = app.query_one("#runs-table", RunsTableView)

            assert status.display is True
            assert runs_table_area.display is False
            assert runs_table.display is False

            for key in ("/", "r", "u", "n", "s"):
                await pilot.press(key)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert status.display is False
            assert runs_table_area.display is True
            assert runs_table.display is True
            assert runs_table.selected_run is not None
            assert runs_table.selected_run.run_id == "run-1234"
            assert runs_table.selected_run.status == "waiting-i"

            await pilot.press("enter")
            await pilot.pause()

            assert status.display is True
            assert runs_table_area.display is False
            assert runs_table.display is False

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_activates_waiting_input_row_from_agents_command() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=ActivatingRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(
                runs=[make_runs_port_item(run_id="run-1234", wait_type="input")]
            ),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            for key in ("/", "a", "g", "e", "n", "t", "s"):
                await pilot.press(key)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            runs_table_area = app.query_one("#runs-table-area")
            runs_table = app.query_one("#runs-table", RunsTableView)
            assert runs_table_area.display is True
            assert runs_table.display is True
            assert runs_table.selected_run is not None
            assert runs_table.selected_run.status == "waiting-i"

            await pilot.press("enter")
            await pilot.pause()

            assert app.state.runs_table_visible is False
            assert app.state.session_key == "run-1234"
            assert app.state.screen_status == ScreenStatus.WAITING
            assert app.state.waiting_prompt == "Write a message."

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_closes_runs_table_with_enter_on_exit_row() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            status = app.query_one("#status", ScreenStatusView)
            runs_table_area = app.query_one("#runs-table-area")
            runs_table = app.query_one("#runs-table", RunsTableView)

            for key in ("/", "r", "u", "n", "s"):
                await pilot.press(key)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("end")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert status.display is True
            assert runs_table_area.display is False
            assert runs_table.display is False

    with patched_to_thread(list_runs_use_case_module):
        asyncio.run(run())


def test_console_screen_routes_arrow_keys_to_visible_autocomplete() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            for key in ("/", "r", "u"):
                await pilot.press(key)
            await pilot.pause()

            autocomplete = app.query_one("#autocomplete", AutoCompleteView)
            assert autocomplete.is_visible() is True
            assert autocomplete.selected_item is not None
            assert autocomplete.selected_item.label == "run"

            await pilot.press("down")
            assert autocomplete.selected_item is not None
            assert autocomplete.selected_item.label == "runs"

            await pilot.press("up")
            assert autocomplete.selected_item is not None
            assert autocomplete.selected_item.label == "run"

    asyncio.run(run())


def test_console_screen_routes_scroll_keys_to_transcript_when_runs_table_is_hidden() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel.state.transcript_items.extend(
            [
                UserInputItem(text="hello"),
                InfoItem(text="world"),
            ]
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            calls: list[str] = []

            def record(name: str):
                def inner(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
                    _ = args
                    _ = kwargs
                    calls.append(name)

                return inner

            transcript.scroll_up = record("up")  # type: ignore[method-assign]
            transcript.scroll_down = record("down")  # type: ignore[method-assign]
            transcript.scroll_page_up = record("pageup")  # type: ignore[method-assign]
            transcript.scroll_page_down = record("pagedown")  # type: ignore[method-assign]
            transcript.scroll_home = record("home")  # type: ignore[method-assign]
            transcript.scroll_end = record("end")  # type: ignore[method-assign]

            await pilot.press("up", "down", "pageup", "pagedown", "home", "end")
            await pilot.pause()

            assert calls == ["up", "down", "pageup", "pagedown", "home", "end"]

    asyncio.run(run())


def test_console_screen_renders_agent_markdown_without_literal_markers() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel.state.transcript_items.extend(
            [
                RunStepItem(
                    run_id="run-1",
                    step_type="agent",
                    step_id="support_agent",
                ),
                RunOutputItem(
                    run_id="run-1",
                    step_type="agent",
                    output='{"text":"Hola **mundo**\\n\\n- **uno**\\n- dos"}',
                    format=OutputFormat.MARKDOWN,
                ),
            ]
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [strip.text.rstrip() for strip in transcript.lines]

            assert rendered_lines[0] == "[agent] support_agent"
            assert rendered_lines[1] == "‹ Hola mundo"
            assert rendered_lines[3] == "   • uno"
            assert rendered_lines[4] == "   • dos"
            assert all("**" not in line for line in rendered_lines)

    asyncio.run(run())


def test_console_screen_renders_agent_fenced_code_block_without_prefixed_backticks() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel.state.transcript_items.extend(
            [
                RunStepItem(
                    run_id="run-1",
                    step_type="agent",
                    step_id="support_agent",
                ),
                RunOutputItem(
                    run_id="run-1",
                    step_type="agent",
                    output=(
                        '{"text":"```diff\\n@@ -1 +1 @@\\n-old\\n+new\\n```\\n\\n'
                        'Cambios:\\n\\n1. Uno"}'
                    ),
                    format=OutputFormat.MARKDOWN,
                ),
            ]
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [strip.text.rstrip() for strip in transcript.lines]

            assert rendered_lines[0] == "[agent] support_agent"
            assert rendered_lines[1] == "‹  @@ -1 +1 @@"
            assert all("```" not in line for line in rendered_lines)
            assert any(line == "‹  @@ -1 +1 @@" for line in rendered_lines)
            assert any(line == "  Cambios:" for line in rendered_lines)

    asyncio.run(run())
