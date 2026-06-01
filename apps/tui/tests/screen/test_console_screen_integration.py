from __future__ import annotations

import asyncio

import pytest
from textual import events
from textual.widgets import Button, Static, TextArea

from apps.tui.tests.support import (
    FakeAgentPort,
    FakeRunsPort,
    NeverCalledRunPort,
    NeverCalledWaitingPort,
    build_viewmodel,
    make_runs_port_item,
    patched_to_thread,
)
from stui.di.strings import TuiStrings
from stui.port.run_port import (
    RunDispatch,
    RunDispatchError,
    RunDispatchErrorKind,
    RunRuntimeStatus,
    RunRuntimeStatusKind,
)
from stui.screen import console_screen as console_screen_module
from stui.screen.action_open_url_view import ActionOpenUrlView
from stui.screen.agent_context_stats_view import AgentContextStatsView
from stui.screen.autocomplete_view import AutoCompleteView
from stui.screen.console_screen import ConsoleScreen
from stui.screen.screen_status_view import ScreenStatusView
from stui.screen.transcript_log import TranscriptLog
from stui.usecase import (
    interrupt_agent_turn_use_case as interrupt_agent_turn_use_case_module,
)
from stui.usecase import run_command_use_case as run_command_use_case_module
from stui.usecase.run_event_context import RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
    AgentContextStatsState,
    AgentStepFinalOutputItem,
    AgentStepStopReason,
    InfoItem,
    NotifyActionState,
    OutputFormat,
    PromptMode,
    RunStepItem,
    StepNotifyOutputItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit

LONG_NOTIFY_ACTION_MESSAGE = (
    "Authorize the app with the external provider. This message is intentionally "
    "long so the TUI notification can show how action text wraps while keeping "
    "the button aligned on the right side."
)


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


def test_console_screen_exits_on_exit_command() -> None:
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
            await pilot.press("/", "e", "x", "i", "t", "enter")
            await pilot.pause()

        assert exited == ["session-123"]

    asyncio.run(run())


def test_console_screen_does_not_exit_on_bare_exit_text() -> None:
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
            await pilot.press("e", "x", "i", "t", "enter")
            await pilot.pause()

        assert exited == []
        assert app.state.transcript.items

    asyncio.run(run())


def test_console_screen_ctrl_c_copies_prompt_selection_without_exiting() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="session-123",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        exited: list[str | None] = []
        copied: list[str] = []

        def fake_exit(result: str | None = None) -> None:
            exited.append(result)

        def fake_copy_to_clipboard(text: str) -> None:
            copied.append(text)

        app.exit = fake_exit  # type: ignore[method-assign]
        app.copy_to_clipboard = fake_copy_to_clipboard  # type: ignore[method-assign]

        async with app.run_test(size=(80, 24)) as pilot:
            prompt = app.query_one("#prompt", TextArea)
            prompt.text = "copy me"
            prompt.select_all()
            prompt.focus()

            await pilot.press("ctrl+c")
            await pilot.pause()

        assert copied == ["copy me"]
        assert exited == []

    asyncio.run(run())


def test_console_screen_ctrl_c_does_not_show_quit_notification() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="session-123",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        exited: list[str | None] = []
        notifications: list[tuple[str, str]] = []

        def fake_exit(result: str | None = None) -> None:
            exited.append(result)

        def fake_notify(
            message: str,
            *,
            title: str = "",
            severity: str = "information",
            timeout: float | None = None,
            markup: bool = True,
        ) -> None:
            _ = severity, timeout, markup
            notifications.append((title, message))

        app.exit = fake_exit  # type: ignore[method-assign]
        app.notify = fake_notify  # type: ignore[method-assign]

        async with app.run_test(size=(80, 24)) as pilot:
            app.set_focus(None)

            await pilot.press("ctrl+c")
            await pilot.pause()

        assert exited == []
        assert notifications == []

    asyncio.run(run())


def test_console_screen_ctrl_q_exits_app() -> None:
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
            await pilot.press("ctrl+q")
            await pilot.pause()

        assert exited == [None]

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


def test_console_screen_pastes_single_line_once_and_strips_trailing_newline() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        command = "/run openai-auth"
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            prompt = app.query_one("#prompt", TextArea)
            prompt.post_message(events.Paste(command))
            await pilot.pause()

            assert prompt.text == command

            prompt.text = ""
            prompt.cursor_location = (0, 0)
            prompt.post_message(events.Paste(f"{command}\n"))
            await pilot.pause()

            assert prompt.text == command

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


def test_console_screen_shows_running_status_after_run_command() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=CreatedRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("/", "r", "u", "n", " ", "c", "h", "a", "t", "enter")
            await pilot.pause()

            status = app.query_one("#status", ScreenStatusView)
            footer_right = app.query_one("#footer-right", Static)
            prompt_row = app.query_one("#prompt-row")
            assert app.state.view_status.kind == ViewStatusKind.RUNNING
            assert "Running" in str(status.render())
            assert footer_right.content == "run-1234\nchat"
            assert footer_right.size.height == 2
            assert status.display is True
            assert status.size.height >= 1
            assert status.region.bottom == prompt_row.region.y

    with patched_to_thread(run_command_use_case_module):
        asyncio.run(run())


def test_console_screen_routes_notify_action_link_to_viewmodel() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        action_state = _notify_action_state()
        calls: list[tuple[str, str, str]] = []

        def record_open_notify_action_link(
            *,
            run_id: str,
            step_id: str,
            url: str,
        ) -> None:
            calls.append((run_id, step_id, url))

        viewmodel.state.set_notify_action(action_state)
        viewmodel.open_notify_action_link = (  # type: ignore[method-assign]
            record_open_notify_action_link
        )
        app = ConsoleScreen(viewmodel=viewmodel)

        async with app.run_test(size=(80, 24)) as pilot:
            status = app.query_one("#status", Static)
            prompt_row = app.query_one("#prompt-row")
            message = app.query_one("#notify-action-message", Static)
            view = app.query_one("#notify-action", ActionOpenUrlView)
            open_link = app.query_one("#notify-action-open-link", Button)
            open_link.focus()

            await pilot.press("enter")
            await pilot.pause()

            assert view.size.width >= 28
            assert status.region.bottom == view.region.bottom
            assert status.region.bottom == prompt_row.region.y
            assert view.region.right == prompt_row.region.right
            assert message.size.height > 1
            assert open_link.region.y > message.region.bottom
            assert open_link.region.right == view.region.right - 2
            assert str(open_link.label) == "Open authorization"

        assert calls == [
            ("run-1", "auth_link", "https://example.com/oauth/start"),
        ]

    asyncio.run(run())


def test_console_screen_routes_notify_action_done_to_viewmodel() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
            strings=TuiStrings(notify_action_done_label="complete"),
        )
        action_state = _notify_action_state()
        calls: list[tuple[str, str]] = []

        def record_done_notify_action(
            *,
            run_id: str,
            step_id: str,
        ) -> None:
            calls.append((run_id, step_id))

        viewmodel.state.set_notify_action(action_state)
        viewmodel.done_notify_action = (  # type: ignore[method-assign]
            record_done_notify_action
        )
        app = ConsoleScreen(
            viewmodel=viewmodel,
            strings=TuiStrings(notify_action_done_label="complete"),
        )

        async with app.run_test(size=(80, 24)) as pilot:
            done = app.query_one("#notify-action-done", Button)

            await pilot.click("#notify-action-done")
            await pilot.pause()

            assert str(done.label) == "complete"

        assert calls == [("run-1", "auth_link")]

    asyncio.run(run())


def test_console_screen_moves_focus_from_prompt_to_notify_action_with_right() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel.state.set_notify_action(_notify_action_state())
        app = ConsoleScreen(viewmodel=viewmodel)

        async with app.run_test(size=(80, 24)) as pilot:
            prompt = app.query_one("#prompt", TextArea)
            done = app.query_one("#notify-action-done", Button)
            prompt.focus()

            await pilot.press("right")
            await pilot.pause()

            assert app.focused is done

    asyncio.run(run())


def test_console_screen_moves_focus_between_notify_action_buttons_with_arrows() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        viewmodel.state.set_notify_action(_notify_action_state())
        app = ConsoleScreen(viewmodel=viewmodel)

        async with app.run_test(size=(80, 24)) as pilot:
            prompt = app.query_one("#prompt", TextArea)
            done = app.query_one("#notify-action-done", Button)
            open_link = app.query_one("#notify-action-open-link", Button)
            done.focus()

            await pilot.press("right")
            await pilot.pause()

            assert app.focused is open_link

            open_link.focus()
            await pilot.press("left")
            await pilot.pause()

            assert app.focused is done

            done.focus()
            await pilot.press("left")
            await pilot.pause()

            assert app.focused is prompt

            open_link.focus()
            await pilot.press("right")
            await pilot.pause()

            assert app.focused is prompt

    asyncio.run(run())


def test_console_screen_keeps_right_arrow_in_prompt_without_notify_action() -> None:
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
            prompt.focus()

            await pilot.press("right")
            await pilot.pause()

            assert app.focused is prompt

    asyncio.run(run())


def _notify_action_state() -> NotifyActionState:
    return NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message=LONG_NOTIFY_ACTION_MESSAGE,
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            url="https://example.com/oauth/start",
        ),
    )


class CreatedRunPort:
    def __init__(self) -> None:
        self.called_with: list[str] = []

    def run(self, raw_args: str) -> RunDispatch:
        self.called_with.append(raw_args)
        return RunDispatch(
            run_id="run-1234",
            status=RunRuntimeStatusKind.CREATED,
            worker_pid=1,
            error=RunDispatchError(kind=RunDispatchErrorKind.NONE, message=""),
        )

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        _ = run_id
        return None


def test_run_console_screen_disables_textual_mouse(monkeypatch: pytest.MonkeyPatch) -> None:
    viewmodel = build_viewmodel(
        session_key="main",
        run_port=NeverCalledRunPort(),
        waiting_port=NeverCalledWaitingPort(),
        runs_port=FakeRunsPort(),
    )
    run_calls: list[dict[str, object]] = []

    class FakeContainer:
        strings = console_screen_module.DEFAULT_TUI_STRINGS

        def build_viewmodel(self, *, session_key: str) -> object:
            return viewmodel

    def fake_build_tui_container(
        *,
        theme: object,
        strings: object,
    ) -> FakeContainer:
        return FakeContainer()

    def fake_run(
        self: ConsoleScreen,
        **kwargs: object,
    ) -> str:
        run_calls.append(kwargs)
        return "main"

    monkeypatch.setattr(
        console_screen_module,
        "build_tui_container",
        fake_build_tui_container,
    )
    monkeypatch.setattr(ConsoleScreen, "run", fake_run)

    result = console_screen_module.run_console_screen(session_key="main")

    assert result == "main"
    assert run_calls == [{"mouse": False}]


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


def test_console_screen_shows_runs_empty_message_from_strings() -> None:
    async def run() -> None:
        strings = TuiStrings(
            runs_table_empty_message="No runs yet. Use /run to execute your flows.",
            runs_table_navigation_hint="↑↓ · Enter · Esc",
        )
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(runs=[]),
            strings=strings,
        )
        app = ConsoleScreen(viewmodel=viewmodel, strings=strings)
        async with app.run_test(size=(100, 24)) as pilot:
            viewmodel.show_runs_table()
            await pilot.pause()

            empty_message = app.query_one("#runs-table-empty", Static)
            navigation_hint = app.query_one("#runs-table-navigation", Static)

            assert app.state.runs_table.visible is True
            assert empty_message.content.plain == (
                "No runs yet. Use /run to execute your flows."
            )
            assert navigation_hint.content.plain == "↑↓ · Enter · Esc"

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


def test_console_screen_clears_agent_context_stats_when_autocomplete_appears() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            viewmodel.state.set_agent_context_stats(
                AgentContextStatsState(
                    entries=24,
                    estimated_tokens=2618,
                    start_sequence=1,
                    end_sequence=24,
                    current_tokens=2618,
                    limit_tokens=80000,
                    capacity_tokens=100000,
                )
            )
            viewmodel.screen_resized()
            await pilot.pause()

            context_stats = app.query_one("#agent-context-stats", AgentContextStatsView)
            assert context_stats.display is True

            viewmodel.prompt_change(text="/", cursor_position=1)
            await pilot.pause()

            autocomplete = app.query_one("#autocomplete", AutoCompleteView)
            assert autocomplete.is_visible() is True
            assert app.state.agent_context_stats is None
            assert context_stats.display is False

            viewmodel.prompt_change(text="", cursor_position=0)
            await pilot.pause()

            assert context_stats.display is False

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
                AgentStepFinalOutputItem(
                    run_id="run-1",
                    step_id="support_agent",
                    stop_reason=AgentStepStopReason.FINAL,
                    final='{"text":"Hola **mundo**\\n\\n- **uno**\\n- dos"}',
                    format=OutputFormat.MARKDOWN,
                ),
            ]
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [strip.text.rstrip() for strip in transcript.lines]
            agent_index = rendered_lines.index("[agent] support_agent")

            assert rendered_lines[agent_index + 1] == "‹ Hola mundo"
            assert rendered_lines[agent_index + 3] == "   • uno"
            assert rendered_lines[agent_index + 4] == "   • dos"
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
                AgentStepFinalOutputItem(
                    run_id="run-1",
                    step_id="support_agent",
                    stop_reason=AgentStepStopReason.FINAL,
                    final=(
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
            agent_index = rendered_lines.index("[agent] support_agent")

            assert rendered_lines[agent_index + 1] == "‹  @@ -1 +1 @@"
            assert all("```" not in line for line in rendered_lines)
            assert any(line == "‹  @@ -1 +1 @@" for line in rendered_lines)
            assert any(line == "  Cambios:" for line in rendered_lines)

    asyncio.run(run())


def test_console_screen_renders_notify_output_like_agent_message() -> None:
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
                    step_type="notify",
                    step_id="show_message",
                ),
                StepNotifyOutputItem(
                    run_id="run-1",
                    step_type="notify",
                    message="Hola mundo",
                    format=OutputFormat.SIMPLE,
                ),
            ]
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [strip.text.rstrip() for strip in transcript.lines]
            notify_index = rendered_lines.index("[notify] show_message")

            assert rendered_lines[notify_index + 1] == "• Hola mundo"

    asyncio.run(run())


def test_console_screen_rerenders_transcript_after_resize() -> None:
    async def run() -> None:
        viewmodel = build_viewmodel(
            session_key="main",
            run_port=NeverCalledRunPort(),
            waiting_port=NeverCalledWaitingPort(),
            runs_port=FakeRunsPort(),
        )
        url = (
            "http://127.0.0.1:8001/webhooks/example-auth/"
            "GrbyVerTlIkPm33R-DbTe_7h3WKNbKkl"
        )
        viewmodel.state.transcript.items.append(
            StepNotifyOutputItem(
                run_id="run-1",
                step_type="notify",
                message=f"Fake authorization mode\n\n```text\n{url}\n```",
                format=OutputFormat.MARKDOWN,
            )
        )
        app = ConsoleScreen(viewmodel=viewmodel)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            transcript = app.query_one("#transcript-log", TranscriptLog)
            rendered_lines = [strip.text.rstrip() for strip in transcript.lines]

            assert any("…" in line for line in rendered_lines)

            await pilot.resize_terminal(120, 24)
            await pilot.pause(0.2)

            rendered_lines = [strip.text.rstrip() for strip in transcript.lines]

            assert any(url in line for line in rendered_lines)

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
            run_name="ant",
            status=RunStatus.WAITING_INPUT,
        )

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
            assert "[inspect] RunContext" in rendered_lines
            assert any('"run_id": "run-1234"' in line for line in rendered_lines)
            assert any('"run_name": "ant"' in line for line in rendered_lines)
            assert any('"status": "waiting_input"' in line for line in rendered_lines)
            assert any('"max_page": 100' in line for line in rendered_lines)
            assert "[inspect] ScreenStatus" in rendered_lines
            assert any('"session_key": "run-1234"' in line for line in rendered_lines)
            assert any('"mode": "chat"' in line for line in rendered_lines)
            assert any('"items_count": 0' in line for line in rendered_lines)
            assert any('"text": "/dev"' in line for line in rendered_lines)
            assert any('"cursor_position": 4' in line for line in rendered_lines)
            assert any('"waiting_prompt": "Write a message."' in line for line in rendered_lines)
            assert any('"kind": "waiting"' in line for line in rendered_lines)

            assert app.state.prompt.text == baseline_state["prompt_text"]
            assert app.state.prompt.mode == baseline_state["prompt_mode"]
            assert app.state.prompt.cursor_position == baseline_state["cursor_position"]
            assert app.state.prompt.waiting_prompt == baseline_state["waiting_prompt"]
            assert app.state.view_status.kind == baseline_state["view_status"]
            assert len(app.state.transcript.items) == baseline_state["transcript_count"]

            prompt = app.query_one("#prompt", TextArea)
            assert prompt.text == "/dev"

    asyncio.run(run())
