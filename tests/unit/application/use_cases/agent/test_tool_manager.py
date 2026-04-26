import pytest

from skiller.application.tools.notify import NotifyToolAdapter, NotifyToolRequest
from skiller.application.tools.shell import ShellToolAdapter, ShellToolRequest
from skiller.application.use_cases.agent.tool_manager import ToolManager
from skiller.application.use_cases.agent.tool_manager_model import AgentToolRequest
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus

pytestmark = pytest.mark.unit


class _FakeShellTool:
    def __init__(
        self,
        *,
        result: ToolResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = "shell"
        self.result = result or ToolResult(
            name="shell",
            status=ToolResultStatus.COMPLETED,
            data={"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
            text="ok",
            error=None,
        )
        self.error = error
        self.execute_calls: list[ShellToolRequest] = []

    def execute(self, request: ShellToolRequest) -> ToolResult:
        self.execute_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class _FakeNotifyTool:
    def __init__(
        self,
        *,
        result: ToolResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = "notify"
        self.result = result or ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )
        self.error = error
        self.execute_calls: list[NotifyToolRequest] = []

    def execute(self, request: NotifyToolRequest) -> ToolResult:
        self.execute_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def _request(
    *,
    tool: str = "shell",
    allowed_tools: list[str] | None = None,
    args: dict[str, object] | None = None,
) -> AgentToolRequest:
    return AgentToolRequest(
        run_id="run-1",
        step_id="support_agent",
        context_id="thread-1",
        turn_id="turn-1",
        tool=tool,
        args=args or {"command": "pwd"},
        allowed_tools=allowed_tools or ["shell"],
    )


def test_router_dispatches_allowed_tool() -> None:
    shell_tool = _FakeShellTool(
        result=ToolResult(
            name="shell",
            status=ToolResultStatus.COMPLETED,
            data={"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
            text="ok",
            error=None,
        )
    )
    router = ToolManager([shell_tool], [ShellToolAdapter()])

    result = router.execute(_request())

    assert result == ToolResult(
        name="shell",
        status=ToolResultStatus.COMPLETED,
        data={"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
        text="ok",
        error=None,
    )
    assert shell_tool.execute_calls == [ShellToolRequest(command="pwd")]


def test_router_rejects_tool_outside_allowlist() -> None:
    router = ToolManager([_FakeShellTool()], [ShellToolAdapter()])

    result = router.execute(
        _request(tool="notify", allowed_tools=["shell"])
    )

    assert result == ToolResult(
        name="notify",
        status=ToolResultStatus.FAILED,
        data={},
        text=None,
        error="Agent tool 'notify' is not allowed in this step",
    )


def test_router_rejects_allowed_but_unconfigured_tool() -> None:
    router = ToolManager([], [])

    result = router.execute(
        _request(tool="notify", allowed_tools=["notify"])
    )

    assert result == ToolResult(
        name="notify",
        status=ToolResultStatus.FAILED,
        data={},
        text=None,
        error="Agent tool 'notify' is not configured",
    )


def test_router_dispatches_notify_tool() -> None:
    notify_tool = _FakeNotifyTool(
        result=ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )
    )
    router = ToolManager([notify_tool], [NotifyToolAdapter()])

    result = router.execute(
        _request(
            tool="notify",
            allowed_tools=["notify"],
            args={"message": "ok"},
        )
        )

    assert result == ToolResult(
        name="notify",
        status=ToolResultStatus.COMPLETED,
        data={"message": "ok"},
        text="ok",
        error=None,
    )
    assert notify_tool.execute_calls == [NotifyToolRequest(message="ok")]


def test_router_rejects_mismatched_result_name() -> None:
    shell_tool = _FakeShellTool(
        result=ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
            text="ok",
            error=None,
        )
    )
    router = ToolManager([shell_tool], [ShellToolAdapter()])

    result = router.execute(_request())

    assert result == ToolResult(
        name="shell",
        status=ToolResultStatus.FAILED,
        data={},
        text=None,
        error="Agent tool 'shell' returned mismatched result name",
    )


def test_router_rejects_duplicate_tool_names() -> None:
    with pytest.raises(ValueError, match="configured more than once"):
        ToolManager(
            [
                _FakeShellTool(),
                _FakeShellTool(),
            ],
            [ShellToolAdapter()],
        )
