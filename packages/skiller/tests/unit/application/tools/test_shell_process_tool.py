from pathlib import Path

import pytest

from skiller.application.tools.shell import ShellProcessTool, ShellToolRequest
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.tool.tool_contract import ToolInput, ToolResult, ToolResultStatus
from skiller.domain.tool.tool_process_model import ToolProcessOutput, ToolProcessRequest

pytestmark = pytest.mark.unit

_GIT_STATUS_OUTPUT = (
    "M docs/README.md\nM packages/skiller/src/skiller/application/agent/agent_runner.py\n"
)


def test_shell_process_tool_schema_defines_json_env_values() -> None:
    tool = ShellProcessTool()

    schema = tool.schema().value
    properties = schema["properties"]

    assert tool.description == (
        "Execute shell commands constrained by configured allowed_commands and allowed_paths."
    )
    assert properties["command"] == {
        "type": "string",
        "description": (
            "Required. Executes a shell command. If it fails, "
            "the executable may not be in allowed_commands."
        ),
    }
    assert properties["cwd"] == {
        "type": "string",
        "description": "Optional working directory inside allowed_paths.",
    }
    assert properties["env"] == {
        "type": "object",
        "additionalProperties": {
            "type": ["string", "number", "boolean", "object", "array", "null"],
        },
        "description": (
            "Optional environment variables for the command. "
            "Strings are passed unchanged; other JSON values are serialized."
        ),
    }
    assert properties["timeout"] == {
        "type": "integer",
        "description": "Optional timeout in seconds.",
    }


def test_shell_process_tool_builds_process_request(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = ShellProcessTool(shell="/bin/zsh")
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(workspace,),
    )

    raw_request = tool.request(
        ToolInput(
            run_id="run-1",
            step_id="support_agent",
            tool_call_id="call-1",
            args={
                "command": "pytest -q",
                "cwd": str(workspace),
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
        cwd=str(workspace),
        env={"CI": "1"},
        timeout=30,
    )


def test_shell_process_tool_serializes_structured_env_values_as_json() -> None:
    tool = ShellProcessTool()

    result = tool.request(
        ToolInput(
            run_id="run-1",
            step_id="inspect_event",
            tool_call_id="call-1",
            args={
                "command": "env",
                "env": {
                    "EVENT": {"kind": "message", "id": 42},
                    "RETRIES": 2,
                    "ENABLED": True,
                    "EMPTY": None,
                    "INPUT_PATH": "/tmp/event.json",
                },
            },
        )
    )

    assert result.ok is True
    assert result.request is not None
    assert result.request.env == {
        "EVENT": '{"kind":"message","id":42}',
        "RETRIES": "2",
        "ENABLED": "true",
        "EMPTY": "null",
        "INPUT_PATH": "/tmp/event.json",
    }


def test_shell_process_tool_rejects_non_json_serializable_env_value() -> None:
    tool = ShellProcessTool()

    result = tool.request(
        ToolInput(
            run_id="run-1",
            step_id="inspect_event",
            tool_call_id="call-1",
            args={
                "command": "env",
                "env": {"INPUT_PATH": Path("/tmp/event.json")},
            },
        )
    )

    assert result.ok is False
    assert result.error == (
        "Tool call 'call-1' requires JSON-serializable value for env 'INPUT_PATH'"
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
    assert result.error == "shell command path escapes allowed_paths: /etc/passwd"


def test_shell_process_tool_rejects_cwd_outside_allowed_paths() -> None:
    tool = ShellProcessTool(shell="/bin/bash")
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
    )

    result = tool.policy(
        config=config,
        request=ShellToolRequest(command="pwd", cwd="/outside/workspace"),
    )

    assert result.ok is False
    assert result.error == "shell cwd escapes allowed_paths: /outside/workspace"


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
    assert result.error == (
        "Command 'pytest' is not in the shell allowlist. "
        "Use an allowed command (git) or ask to add 'pytest' to allowed_commands."
    )


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
