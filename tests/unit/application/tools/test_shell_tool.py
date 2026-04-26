import pytest

from skiller.application.tools.shell import ShellTool, ShellToolRequest
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus

pytestmark = pytest.mark.unit


class _FakeShell:
    def __init__(
        self,
        result: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or {"ok": True, "exit_code": 0, "stdout": "ok", "stderr": ""}
        self.error = error
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


def test_shell_tool_runs_shell() -> None:
    shell = _FakeShell(result={"ok": False, "exit_code": 1, "stdout": "", "stderr": "boom"})
    tool = ShellTool(shell=shell)
    request = ShellToolRequest(
        command="pytest -q",
        cwd="/workspace",
        env={"CI": "1"},
        timeout=30,
    )

    result = tool.execute(request)

    assert result == ToolResult(
        name="shell",
        status=ToolResultStatus.COMPLETED,
        data={
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "boom",
        },
        text="boom",
        error=None,
    )
    assert shell.calls == [
        {
            "command": "pytest -q",
            "cwd": "/workspace",
            "env": {"CI": "1"},
            "timeout": 30,
        }
    ]


def test_shell_tool_propagates_timeout() -> None:
    tool = ShellTool(shell=_FakeShell(error=TimeoutError()))

    with pytest.raises(TimeoutError):
        tool.execute(
            ShellToolRequest(
                command="pytest -q",
                timeout=15,
            )
        )
