import pytest

from skiller.application.agent.tools.tool_manager import ToolManager, ToolPrepareFailure
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.tools.notify import NotifyToolRequest
from skiller.application.tools.shell import ShellProcessTool, ShellToolRequest
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfig,
    ToolSchema,
)

pytestmark = pytest.mark.unit


class _FakeCommandTool(ToolDefinition[ShellToolRequest]):
    name = "shell"
    description = "Fake shell tool"

    def __init__(
        self,
        *,
        result: ToolResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or ToolResult(
            name="shell",
            status=ToolResultStatus.COMPLETED,
            data={"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
            text="ok",
            error=None,
        )
        self.error = error
        self.run_calls: list[ShellToolRequest] = []

    def schema(self) -> ToolSchema:
        return ToolSchema(value={})

    def request(self, input: ToolInput) -> ToolRequestResult[ShellToolRequest]:
        return ToolRequestResult.valid(
            ShellToolRequest(command=input.require_string("command"))
        )

    def run(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: ShellToolRequest,
    ) -> ToolResult:
        self.run_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class _BrokenPolicyTool(_FakeCommandTool):
    def policy(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: ShellToolRequest,
    ):
        _ = request
        raise RuntimeError("policy boom")


class _FakeNotifyTool(ToolDefinition[NotifyToolRequest]):
    name = "notify"
    description = "Fake notify tool"

    def __init__(
        self,
        *,
        result: ToolResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )
        self.error = error
        self.run_calls: list[NotifyToolRequest] = []

    def schema(self) -> ToolSchema:
        return ToolSchema(value={})

    def request(self, input: ToolInput) -> ToolRequestResult[NotifyToolRequest]:
        return ToolRequestResult.valid(
            NotifyToolRequest(message=input.require_string("message"))
        )

    def run(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: NotifyToolRequest,
    ) -> ToolResult:
        self.run_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def _request(
    *,
    tool: str = "shell",
    allowed_tools: list[str] | None = None,
    args: dict[str, object] | None = None,
    runtime_config: ToolRuntimeConfig | None = None,
) -> AgentToolRequest:
    return AgentToolRequest(
        run_id="run-1",
        step_id="support_agent",
        context_id="thread-1",
        turn_id="turn-1",
        tool_call_id="call-1",
        tool=tool,
        args=args or {"command": "pwd"},
        allowed_tools=allowed_tools or ["shell"],
        runtime_config=runtime_config,
    )


def test_router_prepares_allowed_tool_without_executing_it() -> None:
    command_tool = _FakeCommandTool()
    router = ToolManager([command_tool])

    result = router.prepare(_request())

    assert result.ok is True
    assert result.tool_name == "shell"
    assert result.error is None
    assert result.prepared is not None
    assert result.prepared.name == "shell"
    assert result.prepared.tool is command_tool
    assert result.prepared.request == ShellToolRequest(command="pwd")
    assert command_tool.run_calls == []


def test_router_prepares_process_tool_without_run_method() -> None:
    shell_tool = ShellProcessTool(shell="/bin/bash")
    router = ToolManager([shell_tool])

    result = router.prepare(
        _request(
            runtime_config=ShellToolRuntimeConfig(
                definition=ShellProcessTool,
                workspace="/workspace",
            ),
        )
    )

    assert result.ok is True
    assert result.prepared is not None
    assert result.prepared.tool is shell_tool
    assert result.prepared.request == ShellToolRequest(
        command="pwd",
        effective_cwd="/workspace",
    )


def test_router_executes_prepared_tool() -> None:
    command_tool = _FakeCommandTool()
    router = ToolManager([command_tool])
    prepared = router.prepare(_request()).prepared

    assert prepared is not None
    result = router.execute_prepared(prepared)

    assert result == command_tool.result
    assert command_tool.run_calls == [ShellToolRequest(command="pwd")]


def test_router_exposes_tool_definitions_in_allowlist_order() -> None:
    command_tool = _FakeCommandTool()
    notify_tool = _FakeNotifyTool()
    router = ToolManager([command_tool, notify_tool])

    definitions = router.get_tool_definitions(["notify", "shell"])

    assert definitions == [
        notify_tool,
        command_tool,
    ]


def test_router_prepare_rejects_tool_outside_allowlist() -> None:
    router = ToolManager([_FakeCommandTool()])

    result = router.prepare(_request(tool="notify", allowed_tools=["shell"]))

    assert result.ok is False
    assert result.error == ToolPrepareFailure.REQUEST_INVALID
    assert result.error_message == "Tool 'notify' is not allowed in this step"


def test_router_prepare_rejects_policy_blocked_tool() -> None:
    shell_tool = ShellProcessTool(shell="/bin/bash")
    router = ToolManager([shell_tool])

    result = router.prepare(
        _request(
            args={"command": "cat /etc/passwd"},
            runtime_config=ShellToolRuntimeConfig(
                definition=ShellProcessTool,
                workspace="/workspace",
            ),
        )
    )

    assert result.ok is False
    assert result.error == ToolPrepareFailure.POLICY_BLOCKED
    assert result.error_message == "shell command path escapes workspace"


def test_router_prepare_rejects_policy_exception() -> None:
    router = ToolManager([_BrokenPolicyTool()])

    result = router.prepare(_request())

    assert result.ok is False
    assert result.error == ToolPrepareFailure.POLICY_EXCEPTION
    assert result.error_message == "policy boom"


def test_router_prepare_rejects_allowed_but_unconfigured_tool_as_request_failure() -> None:
    router = ToolManager([])

    result = router.prepare(_request(tool="notify", allowed_tools=["notify"]))

    assert result.ok is False
    assert result.error == ToolPrepareFailure.REQUEST_INVALID
    assert result.error_message == "Tool 'notify' is not configured"


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
    router = ToolManager([notify_tool])

    prepared = router.prepare(
        _request(tool="notify", allowed_tools=["notify"], args={"message": "ok"})
    )

    assert prepared.prepared is not None
    result = router.execute_prepared(prepared.prepared)

    assert result == ToolResult(
        name="notify",
        status=ToolResultStatus.COMPLETED,
        data={"message": "ok"},
        text="ok",
        error=None,
    )
    assert notify_tool.run_calls == [NotifyToolRequest(message="ok")]


def test_router_rejects_mismatched_result_name() -> None:
    command_tool = _FakeCommandTool(
        result=ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
            text="ok",
            error=None,
        )
    )
    router = ToolManager([command_tool])

    prepared = router.prepare(_request())

    assert prepared.prepared is not None
    result = router.execute_prepared(prepared.prepared)

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
                _FakeCommandTool(),
                _FakeCommandTool(),
            ]
        )
