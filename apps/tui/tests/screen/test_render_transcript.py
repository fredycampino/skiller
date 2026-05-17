from __future__ import annotations

import pytest
from rich.console import Console

from stui.screen.markdown import MarkdownView
from stui.screen.theme import DEFAULT_TUI_THEME
from stui.screen.transcript.agent_final_assistant_message_view import (
    AgentFinalAssistantMessageView,
)
from stui.screen.transcript.agent_tool_call_view import AgentToolCallView
from stui.screen.transcript.agent_tool_result_view import AgentToolResultView
from stui.screen.transcript.info_view import InfoView
from stui.screen.transcript.render_transcript import RenderTranscript
from stui.viewmodel.console_screen_state import (
    AgentFinalAssistantMessageItem,
    AgentToolCallItem,
    AgentToolResultItem,
    InfoItem,
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


def test_final_assistant_message_view_renders_blank_line() -> None:
    view = AgentFinalAssistantMessageView(
        item=AgentFinalAssistantMessageItem(
            run_id="run-1",
            step_id="agent",
            text="truncated",
            total_tokens=3155,
            max_window_tokens=1000000,
            model="MiniMax-M2.5",
        )
    )
    console = Console(width=80, record=True)

    console.print(view.render(theme=DEFAULT_TUI_THEME))

    assert console.export_text() == "\n"


def test_render_markdown_inline_code_has_no_background() -> None:
    console = Console(width=80, record=True)

    console.print(MarkdownView("Run `pwd` now.", theme=DEFAULT_TUI_THEME).render())

    rendered = console.export_text(styles=True)
    assert "pwd" in rendered
    assert "40m" not in rendered
