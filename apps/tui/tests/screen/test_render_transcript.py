from __future__ import annotations

import pytest

from stui.screen.transcript.agent_tool_call_view import AgentToolCallView
from stui.screen.transcript.agent_tool_result_view import AgentToolResultView
from stui.screen.transcript.info_view import InfoView
from stui.screen.transcript.render_transcript import RenderTranscript
from stui.viewmodel.console_screen_state import (
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
