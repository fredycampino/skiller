from __future__ import annotations

import pytest
from rich.console import Console
from rich.text import Text

from stui.screen.markdown import MarkdownView
from stui.screen.theme import DEFAULT_TUI_THEME
from stui.screen.transcript.agent_final_assistant_message_view import (
    AgentFinalAssistantMessageView,
)
from stui.screen.transcript.agent_tool_call_view import AgentToolCallView
from stui.screen.transcript.agent_tool_result_view import AgentToolResultView
from stui.screen.transcript.info_view import InfoView
from stui.screen.transcript.render_transcript import RenderTranscript
from stui.screen.transcript.run_status_view import RunStatusView
from stui.screen.transcript.run_waiting_input_view import RunWaitingInputView
from stui.screen.transcript.step_notify_output_view import StepNotifyOutputView
from stui.screen.transcript.step_output_view import StepOutputView
from stui.screen.transcript.step_shell_output_view import StepShellOutputView
from stui.viewmodel.console_screen_state import (
    AgentFinalAssistantMessageItem,
    AgentToolCallItem,
    AgentToolResultItem,
    InfoItem,
    RunStatusItem,
    RunWaitingInputItem,
    StepNotifyOutputItem,
    StepOutputItem,
    StepShellOutputItem,
)

pytestmark = pytest.mark.unit


def test_active_tool_marks_call_when_call_is_latest_view() -> None:
    call = AgentToolCallView(
        item=AgentToolCallItem(
            run_id="run-1",
            step_id="agent",
            tool="shell",
            command="ls packages/skiller/docs/agent",
        )
    )

    views = RenderTranscript()._active_tool(views=[call])  # noqa: SLF001

    assert isinstance(views[0], AgentToolCallView)
    assert views[0].active is True


def test_active_tool_keeps_call_active_while_result_is_latest_view() -> None:
    call = AgentToolCallView(
        item=AgentToolCallItem(
            run_id="run-1",
            step_id="agent",
            tool="shell",
            command="ls packages/skiller/docs/agent",
        )
    )
    result = AgentToolResultView(
        item=AgentToolResultItem(
            run_id="run-1",
            tool="shell",
            preview="agent-config.md",
        )
    )

    views = RenderTranscript()._active_tool(views=[call, result])  # noqa: SLF001

    assert isinstance(views[0], AgentToolCallView)
    assert views[0].active is True
    assert views[1] is result


def test_active_tool_stops_after_non_tool_view() -> None:
    call = AgentToolCallView(
        item=AgentToolCallItem(
            run_id="run-1",
            step_id="agent",
            tool="shell",
            command="ls packages/skiller/docs/agent",
        )
    )
    info = InfoView(item=InfoItem(text="done"))

    views = RenderTranscript()._active_tool(views=[call, info])  # noqa: SLF001

    assert views[0] is call
    assert call.active is False
    assert views[1] is info


def test_active_notify_marks_latest_notify_as_primary() -> None:
    previous = StepNotifyOutputView(
        item=StepNotifyOutputItem(
            run_id="run-1",
            step_type="notify",
            message="First",
            muted=False,
        )
    )
    latest = StepNotifyOutputView(
        item=StepNotifyOutputItem(
            run_id="run-1",
            step_type="notify",
            message="Second",
            muted=True,
        )
    )

    views = RenderTranscript()._active_notify(views=[previous, latest])  # noqa: SLF001

    assert isinstance(views[0], StepNotifyOutputView)
    assert isinstance(views[1], StepNotifyOutputView)
    assert views[0].item.muted is True
    assert views[1].item.muted is False


def test_active_notify_mutes_all_notify_when_latest_view_is_not_notify() -> None:
    notify = StepNotifyOutputView(
        item=StepNotifyOutputItem(
            run_id="run-1",
            step_type="notify",
            message="First",
            muted=False,
        )
    )
    info = InfoView(item=InfoItem(text="done"))

    views = RenderTranscript()._active_notify(views=[notify, info])  # noqa: SLF001

    assert isinstance(views[0], StepNotifyOutputView)
    assert views[0].item.muted is True
    assert views[1] is info


def test_active_notify_keeps_latest_notify_primary_before_wait() -> None:
    notify = StepNotifyOutputView(
        item=StepNotifyOutputItem(
            run_id="run-1",
            step_type="notify",
            message="First",
            muted=True,
        )
    )
    wait = RunWaitingInputView(
        item=RunWaitingInputItem(
            run_id="run-1",
            step_type="wait_input",
            step_id="ask",
            prompt="Continue?",
        )
    )

    views = RenderTranscript()._active_notify(views=[notify, wait])  # noqa: SLF001

    assert isinstance(views[0], StepNotifyOutputView)
    assert views[0].item.muted is False
    assert views[1] is wait


def test_active_step_output_marks_latest_step_output_as_primary() -> None:
    previous = StepOutputView(
        item=StepOutputItem(
            run_id="run-1",
            step_type="assign",
            output="Values assigned.",
            muted=False,
        )
    )
    latest = StepOutputView(
        item=StepOutputItem(
            run_id="run-1",
            step_type="switch",
            output="when_sample.",
            muted=True,
        )
    )

    views = RenderTranscript()._active_step_output(views=[previous, latest])  # noqa: SLF001

    assert isinstance(views[0], StepOutputView)
    assert isinstance(views[1], StepOutputView)
    assert views[0].item.muted is True
    assert views[1].item.muted is False


def test_active_step_output_marks_latest_shell_output_as_primary() -> None:
    previous = StepOutputView(
        item=StepOutputItem(
            run_id="run-1",
            step_type="assign",
            output="Values assigned.",
            muted=False,
        )
    )
    latest = StepShellOutputView(
        item=StepShellOutputItem(
            run_id="run-1",
            step_type="shell",
            output="ready",
            muted=True,
        )
    )

    views = RenderTranscript()._active_step_output(views=[previous, latest])  # noqa: SLF001

    assert isinstance(views[0], StepOutputView)
    assert isinstance(views[1], StepShellOutputView)
    assert views[0].item.muted is True
    assert views[1].item.muted is False


def test_active_step_output_keeps_latest_step_output_primary_before_wait() -> None:
    output = StepOutputView(
        item=StepOutputItem(
            run_id="run-1",
            step_type="when",
            output="good_notice.",
            muted=True,
        )
    )
    wait = RunWaitingInputView(
        item=RunWaitingInputItem(
            run_id="run-1",
            step_type="wait_input",
            step_id="ask",
            prompt="Continue?",
        )
    )

    views = RenderTranscript()._active_step_output(views=[output, wait])  # noqa: SLF001

    assert isinstance(views[0], StepOutputView)
    assert views[0].item.muted is False
    assert views[1] is wait


def test_active_step_output_mutes_all_step_outputs_when_latest_view_is_not_step_output(
) -> None:
    output = StepOutputView(
        item=StepOutputItem(
            run_id="run-1",
            step_type="assign",
            output="Values assigned.",
            muted=False,
        )
    )
    info = InfoView(item=InfoItem(text="done"))

    views = RenderTranscript()._active_step_output(views=[output, info])  # noqa: SLF001

    assert isinstance(views[0], StepOutputView)
    assert views[0].item.muted is True
    assert views[1] is info


def test_final_assistant_message_view_renders_blank_line() -> None:
    view = AgentFinalAssistantMessageView(
        item=AgentFinalAssistantMessageItem(
            run_id="run-1",
            step_id="agent",
            text="truncated",
            total_tokens=3155,
        )
    )
    console = Console(width=80, record=True)

    console.print(view.render(theme=DEFAULT_TUI_THEME))

    assert console.export_text() == "\n"


def test_run_status_view_renders_finished_as_muted_text() -> None:
    view = RunStatusView(item=RunStatusItem(run_id="run-1", status="succeeded"))

    renderable = view.render(theme=DEFAULT_TUI_THEME)

    assert isinstance(renderable, Text)
    assert renderable.plain == "  Run finished"
    assert str(renderable.style) == DEFAULT_TUI_THEME.color_text_muted


def test_render_markdown_inline_code_has_no_background() -> None:
    console = Console(width=80, record=True)

    console.print(MarkdownView("Run `pwd` now.", theme=DEFAULT_TUI_THEME).render())

    rendered = console.export_text(styles=True)
    assert "pwd" in rendered
    assert "40m" not in rendered
