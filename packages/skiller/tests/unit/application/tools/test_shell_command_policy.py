from pathlib import Path

import pytest

from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool

pytestmark = pytest.mark.unit


def test_shell_command_policy_resolves_relative_cwd_inside_allowed_path(tmp_path) -> None:
    allowed = tmp_path / "workspace"
    child = allowed / "child"
    child.mkdir(parents=True)

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(allowed,),
        )
    )

    assert policy.resolve_cwd("child") == str(child)


def test_shell_command_policy_resolves_absolute_cwd_inside_second_allowed_path(
    tmp_path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    child = second / "child"
    first.mkdir()
    child.mkdir(parents=True)

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(first, second),
        )
    )

    assert policy.resolve_cwd(str(child)) == str(child)


def test_shell_command_policy_rejects_cwd_outside_allowed_paths(tmp_path) -> None:
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(allowed,),
        )
    )

    with pytest.raises(ValueError, match="shell cwd escapes allowed_paths"):
        policy.resolve_cwd("../outside")


def test_shell_command_policy_rejects_nonexistent_cwd_inside_allowed_path(tmp_path) -> None:
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    missing = allowed / "missing"
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(allowed,),
        )
    )

    with pytest.raises(ValueError, match=f"shell cwd does not exist: {missing}"):
        policy.resolve_cwd("missing")


def test_shell_command_policy_rejects_file_cwd_inside_allowed_path(tmp_path) -> None:
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    file_path = allowed / "file.txt"
    file_path.touch()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(allowed,),
        )
    )

    with pytest.raises(ValueError, match=f"shell cwd is not a directory: {file_path}"):
        policy.resolve_cwd("file.txt")


def test_shell_command_policy_validates_each_allowlisted_segment() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
            allowlist_enabled=True,
            allowed_commands=("printf", "cat"),
        )
    )

    policy.validate_command(
        command="printf 'hello' | cat",
        effective_cwd="/workspace",
        environment={},
    )


def test_shell_command_policy_rejects_non_allowlisted_segment() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
            allowlist_enabled=True,
            allowed_commands=("printf",),
        )
    )

    with pytest.raises(ValueError, match="'cat' is not in the shell allowlist"):
        policy.validate_command(
            command="printf 'hello' | cat",
            effective_cwd="/workspace",
            environment={},
        )


def test_shell_command_policy_accepts_command_path_inside_second_allowed_path(
    tmp_path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    target = second / "logs.txt"
    first.mkdir()
    second.mkdir()

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(first, second),
            allowlist_enabled=True,
            allowed_commands=("cat",),
        )
    )

    policy.validate_command(
        command=f"cat {target}",
        effective_cwd=str(first),
        environment={},
    )


def test_shell_command_policy_rejects_command_path_outside_allowed_paths(
    tmp_path,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside.txt"
    allowed.mkdir()

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(allowed,),
            allowlist_enabled=True,
            allowed_commands=("cat",),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command=f"cat {outside}",
            effective_cwd=str(allowed),
            environment={},
        )


def test_shell_command_policy_reports_command_parse_error() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "shell command could not be parsed safely: No closing quotation. "
            "Check quotes and heredoc delimiters."
        ),
    ):
        policy.validate_command(
            command="python - <<'PY",
            effective_cwd="/workspace",
            environment={},
        )


def test_shell_command_policy_allows_dev_null_output_redirection() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )

    policy.validate_command(
        command="printf ok >/dev/null 2>&1",
        effective_cwd="/workspace",
        environment={},
    )


def test_shell_command_policy_allows_dev_null_input_redirection() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )

    policy.validate_command(
        command="cat < /dev/null",
        effective_cwd="/workspace",
        environment={},
    )


def test_shell_command_policy_rejects_neighboring_dev_path() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command="printf ok > /dev/random",
            effective_cwd="/workspace",
            environment={},
        )


def test_shell_command_policy_expands_home_in_allowed_paths(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repo = home / "repo"
    repo.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(repo,),
        )
    )

    assert policy.resolve_cwd("~/repo") == str(repo)


def test_shell_command_policy_does_not_validate_executable_as_command_path() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
            allowlist_enabled=True,
            allowed_commands=("python",),
        )
    )

    policy.validate_command(
        command="./.venv/bin/python -m hatchling build",
        effective_cwd="/workspace",
        environment={},
    )


def test_shell_command_policy_blocks_symlink_pointing_outside_allowed_root(tmp_path) -> None:
    real_python = tmp_path / "usr" / "bin" / "python3.12"
    real_python.parent.mkdir(parents=True)
    real_python.write_text("", encoding="utf-8")
    workspace = tmp_path / "workspace"
    venv_bin = workspace / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    venv_python = venv_bin / "python"
    venv_python.symlink_to(real_python)

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace,),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command=f'"{venv_python}" --version',
            effective_cwd=str(workspace),
            environment={},
        )


def test_shell_command_policy_still_blocks_path_outside_allowed_roots(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace,),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command="cat /etc/passwd",
            effective_cwd=str(workspace),
            environment={},
        )


def test_shell_command_policy_allows_env_assignment_path_inside_allowed_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace.resolve(),),
        )
    )

    policy.validate_command(
        command=f"CONFIG_FILE={workspace}/config.json python3 script.py",
        effective_cwd=str(workspace),
        environment={},
    )


def test_shell_command_policy_blocks_env_assignment_path_outside_allowed_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace.resolve(),),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command=f"CONFIG_FILE={outside}/config.json python3 script.py",
            effective_cwd=str(workspace),
            environment={},
        )


@pytest.mark.parametrize("variable_reference", ("$TARGET_DIR", "${TARGET_DIR}"))
def test_shell_command_policy_blocks_expanded_path_outside_allowed_root(
    tmp_path,
    variable_reference: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace.resolve(),),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command=f"ls {variable_reference}/child",
            effective_cwd=str(workspace),
            environment={"TARGET_DIR": str(outside)},
        )


@pytest.mark.parametrize("variable_reference", ("$TARGET_DIR", "${TARGET_DIR}"))
def test_shell_command_policy_allows_expanded_path_inside_allowed_root(
    tmp_path,
    variable_reference: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace.resolve(),),
        )
    )

    policy.validate_command(
        command=f"ls {variable_reference}/child",
        effective_cwd=str(workspace),
        environment={"TARGET_DIR": str(workspace)},
    )


def test_shell_command_policy_allows_tilde_path_inside_allowed_root(tmp_path) -> None:
    home = tmp_path / "home"
    workspace = home / "workspace"
    workspace.mkdir(parents=True)
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace,),
        )
    )

    policy.validate_command(
        command="cat ~/workspace/file",
        effective_cwd=str(workspace),
        environment={"HOME": str(home)},
    )


def test_shell_command_policy_blocks_tilde_path_outside_allowed_root(tmp_path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    home.mkdir()
    workspace.mkdir()
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(workspace,),
        )
    )

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command="cat ~/file",
            effective_cwd=str(workspace),
            environment={"HOME": str(home)},
        )


@pytest.mark.parametrize("reference", ("~+", "~-", "~other"))
def test_shell_command_policy_blocks_unsupported_tilde_expansion(
    reference: str,
) -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )

    with pytest.raises(ValueError, match="unsupported tilde expansion"):
        policy.validate_command(
            command=f"cat {reference}/file",
            effective_cwd="/workspace",
            environment={"HOME": "/workspace"},
        )


def test_shell_command_policy_ignores_literal_quoted_tilde_path() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )

    policy.validate_command(
        command="printf '~/file'",
        effective_cwd="/workspace",
        environment={"HOME": "/outside"},
    )


def test_shell_command_policy_ignores_literal_heredoc_body() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
            allowlist_enabled=True,
            allowed_commands=("cat",),
        )
    )
    command = "cat <<'EOF'\n~/file\n/outside/file\nsudo reboot\n$ROOT/file\nEOF"

    policy.validate_command(
        command=command,
        effective_cwd="/workspace",
        environment={"ROOT": "/outside"},
    )


def test_shell_command_policy_validates_visible_path_after_heredoc() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )
    command = "cat <<'EOF'\n~/literal\nEOF\ncat /outside/file"

    with pytest.raises(ValueError, match="shell command path escapes allowed_paths"):
        policy.validate_command(
            command=command,
            effective_cwd="/workspace",
            environment={},
        )


def test_shell_command_policy_rejects_unquoted_heredoc() -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(Path("/workspace"),),
        )
    )
    command = "cat <<EOF\n~/file\nEOF"

    with pytest.raises(
        ValueError,
        match="unsupported unquoted heredoc delimiter: EOF",
    ):
        policy.validate_command(
            command=command,
            effective_cwd="/workspace",
            environment={"HOME": "/outside"},
        )
