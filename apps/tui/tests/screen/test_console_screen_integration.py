from __future__ import annotations

import asyncio

import pytest
from textual import events
from textual.widgets import Static, TextArea

from apps.tui.tests.support import (
    FakeAgentPort,
    FakeRunsPort,
    NeverCalledRunPort,
    NeverCalledWaitingPort,
    build_viewmodel,
    make_runs_port_item,
    patched_to_thread,
)
from stui.screen.autocomplete_view import AutoCompleteView
from stui.screen.console_screen import ConsoleScreen
from stui.screen.transcript_log import TranscriptLog
from stui.usecase import (
    interrupt_agent_turn_use_case as interrupt_agent_turn_use_case_module,
)
from stui.usecase.run_event_context import RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    InfoItem,
    OutputFormat,
    PromptMode,
    RunOutputItem,
    RunResumeItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
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
            assert app.state.view_status.kind == ViewStatusKind.HIDDEN
            assert isinstance(app.state.transcript.items[0], UserInputItem)
            assert isinstance(app.state.transcript.items[1], InfoItem)

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


def test_console_screen_compacts_multiline_paste_into_single_line_reference() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            prompt = app.query_one("#prompt", TextArea)
            prompt.post_message(events.Paste("linea asdasdasd\nsegunda linea\ntercera linea"))
            await pilot.pause()

            assert prompt.text == "[paste #1 +2 lines]"
            assert app.state.prompt.text == "linea asdasdasd\nsegunda linea\ntercera linea"

            prompt.post_message(events.Paste("uno\ndos"))
            await pilot.pause()

            assert prompt.text == "[paste #1 +2 lines][paste #2 +1 line]"
            assert (
                app.state.prompt.text
                == "linea asdasdasd\nsegunda linea\ntercera lineauno\ndos"
            )

    asyncio.run(run())


def test_console_screen_submits_decoded_multiline_paste_text() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            prompt = app.query_one("#prompt", TextArea)
            prompt.post_message(events.Paste("linea asdasdasd\nsegunda linea\ntercera linea"))
            await pilot.pause()

            assert prompt.text == "[paste #1 +2 lines]"

            await pilot.press("enter")
            await pilot.pause()

            assert prompt.text == ""
            assert isinstance(app.state.transcript.items[0], UserInputItem)
            assert (
                app.state.transcript.items[0].text
                == "linea asdasdasd\nsegunda linea\ntercera linea"
            )

    asyncio.run(run())


def test_console_screen_shows_command_hint_and_session_id_in_footer() -> None:
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
            assert footer_left.content == "/ for commands"
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


def test_console_screen_escape_interrupts_running_chat_agent() -> None:
    async def run() -> None:
        agent_port = FakeAgentPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
            agent_port=agent_port,
        )
        viewmodel._run_event_context.run_id = "run-1234"  # noqa: SLF001
        viewmodel._run_event_context.mode = RunMode.CHAT  # noqa: SLF001
        viewmodel._run_event_context.status = RunStatus.RUNNING  # noqa: SLF001
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            _ = pilot
            await app.action_handle_escape()
            await pilot.pause()

            assert agent_port.called_with == ["run-1234"]

    with patched_to_thread(interrupt_agent_turn_use_case_module):
        asyncio.run(run())


def test_console_screen_escape_closes_runs_table_before_interrupting() -> None:
    async def run() -> None:
        agent_port = FakeAgentPort()
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
            agent_port=agent_port,
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            viewmodel.show_runs_table()
            await pilot.pause()

            assert app.state.runs_table.visible is True

            await app.action_handle_escape()
            await pilot.pause()

            assert app.state.runs_table.visible is False
            assert agent_port.called_with == []

    with patched_to_thread(interrupt_agent_turn_use_case_module):
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
        viewmodel.state.transcript.items.extend(
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
        viewmodel.state.transcript.items.extend(
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
        viewmodel.state.transcript.items.extend(
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


def test_console_screen_hides_resume_and_switch_steps_in_chat_mode() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel._run_event_context.mode = RunMode.CHAT  # noqa: SLF001
        viewmodel.state.transcript.items.extend(
            [
                UserInputItem(text="hola"),
                RunResumeItem(run_id="run-1", skill="agent_tools"),
                RunStepItem(
                    run_id="run-1",
                    step_type="switch",
                    step_id="decide_exit",
                ),
                RunOutputItem(
                    run_id="run-1",
                    step_type="switch",
                    output=(
                        '{"text":"Route selected: support_agent.",'
                        '"value":{"next_step_id":"support_agent"}}'
                    ),
                ),
                RunStepItem(
                    run_id="run-1",
                    step_type="agent",
                    step_id="support_agent",
                ),
            ]
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [
                strip.text.rstrip()
                for strip in transcript.lines
                if strip.text.rstrip()
            ]

            assert rendered_lines == [
                "› hola",
                "[agent] support_agent",
            ]

    asyncio.run(run())


def test_console_screen_renders_local_dev_status_without_mutating_state() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="run-1234",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel.state.transcript.mode = TranscriptMode.CHAT
        viewmodel.state.prompt.mode = PromptMode.DEFAULT
        viewmodel.state.prompt.waiting_prompt = "Write a message."
        viewmodel.state.view_status.kind = ViewStatusKind.WAITING
        viewmodel._run_event_context.activate_run(  # noqa: SLF001
            "run-1234",
            skill_name="ant",
            mode=RunMode.CHAT,
            status=RunStatus.WAITING_INPUT,
        )
        viewmodel._run_event_context.event_ids = {"evt-1", "evt-2"}  # noqa: SLF001

        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            for key in ("/", "d", "e", "v"):
                await pilot.press(key)
            await pilot.pause()

            baseline_state = {
                "prompt_text": app.state.prompt.text,
                "prompt_mode": app.state.prompt.mode,
                "cursor_position": app.state.prompt.cursor_position,
                "waiting_prompt": app.state.prompt.waiting_prompt,
                "view_status": app.state.view_status.kind,
                "transcript_count": len(app.state.transcript.items),
            }

            await pilot.press("enter")
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [
                strip.text.rstrip()
                for strip in transcript.lines
                if strip.text.rstrip()
            ]

            assert "› /dev" in rendered_lines
            assert "[dev] RunEventContext" in rendered_lines
            assert any('"run_id": "run-1234"' in line for line in rendered_lines)
            assert any('"skill_name": "ant"' in line for line in rendered_lines)
            assert "[dev] ConsoleScreenState" in rendered_lines
            assert any('"mode": "chat"' in line for line in rendered_lines)
            assert any('"items_count": 0' in line for line in rendered_lines)

            assert app.state.prompt.text == baseline_state["prompt_text"]
            assert app.state.prompt.mode == baseline_state["prompt_mode"]
            assert app.state.prompt.cursor_position == baseline_state["cursor_position"]
            assert app.state.prompt.waiting_prompt == baseline_state["waiting_prompt"]
            assert app.state.view_status.kind == baseline_state["view_status"]
            assert len(app.state.transcript.items) == baseline_state["transcript_count"]

            prompt = app.query_one("#prompt", TextArea)
            assert prompt.text == "/dev"

    asyncio.run(run())
