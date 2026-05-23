import pytest

from skiller.application.tools.notify import NotifyTool
from skiller.domain.tool.tool_contract import (
    ToolInput,
    ToolResult,
    ToolResultStatus,
)

pytestmark = pytest.mark.unit


def test_notify_tool_returns_result() -> None:
    tool = NotifyTool()
    request = tool.request(
        ToolInput(
            run_id="run-1",
            step_id="notify",
            tool_call_id="notify",
            args={"message": "ok"},
        )
    )
    assert request.ok is True
    assert request.request is not None

    result = tool.run(
        config=None,
        request=request.request,
    )

    assert result == ToolResult(
        name="notify",
        status=ToolResultStatus.COMPLETED,
        data={"message": "ok"},
        text="ok",
        error=None,
    )
