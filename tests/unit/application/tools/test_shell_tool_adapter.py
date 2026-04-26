import pytest

from skiller.application.tools.shell import ShellToolAdapter, ShellToolRequest

pytestmark = pytest.mark.unit


def test_shell_tool_adapter_builds_request() -> None:
    adapter = ShellToolAdapter()

    request = adapter.build_request(
        step_id="support_agent",
        value={
            "command": "pytest -q",
            "cwd": "/workspace",
            "env": {"CI": 1},
            "timeout": 30,
        },
    )

    assert request == ShellToolRequest(
        command="pytest -q",
        cwd="/workspace",
        env={"CI": "1"},
        timeout=30,
    )


def test_shell_tool_adapter_rejects_missing_command() -> None:
    adapter = ShellToolAdapter()

    with pytest.raises(ValueError, match="requires command"):
        adapter.build_request(step_id="support_agent", value={})


def test_shell_tool_adapter_rejects_invalid_env() -> None:
    adapter = ShellToolAdapter()

    with pytest.raises(ValueError, match="env must be an object"):
        adapter.build_request(step_id="support_agent", value={"command": "pwd", "env": "bad"})
