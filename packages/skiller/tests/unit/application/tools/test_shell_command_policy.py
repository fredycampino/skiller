import pytest

from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool

pytestmark = pytest.mark.unit


def test_shell_command_policy_resolves_relative_cwd_inside_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    child = workspace / "child"
    child.mkdir(parents=True)

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            workspace=str(workspace),
        )
    )

    assert policy.resolve_cwd("child") == str(child)


def test_shell_command_policy_rejects_cwd_outside_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            workspace=str(workspace),
        )
    )

    with pytest.raises(ValueError, match="shell cwd escapes workspace"):
        policy.resolve_cwd("../outside")


def test_shell_command_policy_validates_each_allowlisted_segment() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            workspace="/workspace",
            allowlist_enabled=True,
            allowed_commands=("printf", "cat"),
        )
    )

    policy.validate_command(
        command="printf 'hello' | cat",
        effective_cwd="/workspace",
    )


def test_shell_command_policy_rejects_non_allowlisted_segment() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            workspace="/workspace",
            allowlist_enabled=True,
            allowed_commands=("printf",),
        )
    )

    with pytest.raises(ValueError, match="'cat' is not allowed"):
        policy.validate_command(
            command="printf 'hello' | cat",
            effective_cwd="/workspace",
        )
