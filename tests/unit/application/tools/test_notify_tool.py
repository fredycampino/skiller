import pytest

from skiller.application.tools.notify import NotifyTool, NotifyToolRequest
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus

pytestmark = pytest.mark.unit


def test_notify_tool_returns_result() -> None:
    tool = NotifyTool()
    request = NotifyToolRequest(message="ok")

    result = tool.execute(request)

    assert result == ToolResult(
        name="notify",
        status=ToolResultStatus.COMPLETED,
        data={"message": "ok"},
        text="ok",
        error=None,
    )
