from pathlib import Path

import pytest

from skiller.application.tools.shell import ShellProcessTool, ShellToolRequest
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.tool.tool_contract import ToolInput, ToolResult, ToolResultStatus
from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest

pytestmark = pytest.mark.unit

_GIT_STATUS_OUTPUT = (
    "M docs/README.md\n"
    "M packages/skiller/src/skiller/application/agent/agent_runner.py\n"
)


def test_shell_process_tool_builds_process_request() -> None:
    tool = ShellProcessTool(shell="/bin/zsh")
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
    )

    raw_request = tool.request(
        ToolInput(
            run_id="run-1",
            step_id="support_agent",
            tool_call_id="call-1",
            args={
                "command": "pytest -q",
                "cwd": "/workspace",
                "env": {"CI": "1"},
                "timeout": 30,
            },
        )
    )
    assert raw_request.ok is True
    assert raw_request.request is not None
    policy_result = tool.policy(
        config=config,
        request=raw_request.request,
    )

    assert policy_result.ok is True
    assert policy_result.request is not None
    request = tool.call(
        config=config,
        request=policy_result.request,
    )

    assert request == ToolProcessRequest(
        command=["/bin/zsh", "-lc", "pytest -q"],
        cwd="/workspace",
        env={"CI": "1"},
        timeout=30,
    )


def test_shell_process_tool_rejects_command_outside_allowed_paths() -> None:
    tool = ShellProcessTool(shell="/bin/bash")
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
    )

    result = tool.policy(
        config=config,
        request=ShellToolRequest(command="cat /etc/passwd"),
    )

    assert result.ok is False
    assert result.error == "shell command path escapes allowed_paths"


def test_shell_process_tool_rejects_command_outside_allowlist() -> None:
    tool = ShellProcessTool(shell="/bin/bash")
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=True,
        allowed_commands=("git",),
    )

    result = tool.policy(
        config=config,
        request=ShellToolRequest(command="pytest -q"),
    )

    assert result.ok is False
    assert result.error == "shell command blocked by allowlist policy: 'pytest' is not allowed"


def test_shell_process_tool_builds_result_from_output() -> None:
    tool = ShellProcessTool(shell="/bin/bash")

    result = tool.result(
        ToolProcessOutput(
            exit_code=1,
            stdout="",
            stderr="boom",
        )
    )

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


def test_shell_process_tool_keeps_full_stdout_in_text() -> None:
    tool = ShellProcessTool(shell="/bin/bash")

    result = tool.result(
        ToolProcessOutput(
            exit_code=0,
            stdout=_GIT_STATUS_OUTPUT,
            stderr="",
        )
    )

    assert result == ToolResult(
        name="shell",
        status=ToolResultStatus.COMPLETED,
        data={
            "ok": True,
            "exit_code": 0,
            "stdout": _GIT_STATUS_OUTPUT,
            "stderr": "",
        },
        text=_GIT_STATUS_OUTPUT.rstrip(),
        error=None,
    )


def test_shell_process_tool_reports_success_without_stdout() -> None:
    tool = ShellProcessTool(shell="/bin/bash")

    result = tool.result(
        ToolProcessOutput(
            exit_code=0,
            stdout="",
            stderr="",
        )
    )

    assert result.text == "Command completed successfully."
