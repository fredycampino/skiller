import pytest

from skiller.infrastructure.tools.shell.default_shell import DefaultShellRunner

pytestmark = pytest.mark.unit


def test_default_shell_runner_executes_command_and_captures_output() -> None:
    runner = DefaultShellRunner()

    result = runner.run(
        command="printf 'hello'; printf 'warn' >&2",
    )

    assert result == {
        "ok": True,
        "exit_code": 0,
        "stdout": "hello",
        "stderr": "warn",
    }


def test_default_shell_runner_raises_timeout_error() -> None:
    runner = DefaultShellRunner()

    with pytest.raises(TimeoutError, match="timed out after 1s"):
        runner.run(
            command="python3 -c 'import time; time.sleep(2)'",
            timeout=1,
        )


def test_default_shell_runner_blocks_critical_commands() -> None:
    runner = DefaultShellRunner()

    with pytest.raises(ValueError, match="blocked by security policy"):
        runner.run(command="sudo rm -rf /")


def test_default_shell_runner_blocks_paths_outside_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = DefaultShellRunner(workspace_root=str(workspace))

    with pytest.raises(ValueError, match="outside workspace root"):
        runner.run(command="cat /etc/passwd")


def test_default_shell_runner_allows_paths_inside_workspace(
    tmp_path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sample = workspace / "hello.txt"
    sample.write_text("ok", encoding="utf-8")

    runner = DefaultShellRunner(workspace_root=str(workspace))
    result = runner.run(command="cat ./hello.txt")

    assert result["ok"] is True
    assert result["stdout"] == "ok"


def test_default_shell_runner_blocks_disallowed_executable_with_allowlist() -> None:
    runner = DefaultShellRunner(
        allowlist_enabled=True,
        allowed_commands=["git", "rg"],
    )

    with pytest.raises(ValueError, match="allowlist policy"):
        runner.run(command="python3 -V")


def test_default_shell_runner_allows_all_segments_when_allowlisted() -> None:
    runner = DefaultShellRunner(
        allowlist_enabled=True,
        allowed_commands=["printf", "cat"],
    )

    result = runner.run(command="printf 'a' | cat")

    assert result["ok"] is True
    assert result["stdout"] == "a"


def test_default_shell_runner_allows_env_prefix_when_configured() -> None:
    runner = DefaultShellRunner(
        allowlist_enabled=True,
        allowed_commands=["printf"],
        allow_env_prefix=True,
    )

    result = runner.run(command="FOO=bar printf 'ok'")

    assert result["ok"] is True
    assert result["stdout"] == "ok"


def test_default_shell_runner_blocks_env_prefix_when_disabled() -> None:
    runner = DefaultShellRunner(
        allowlist_enabled=True,
        allowed_commands=["printf"],
        allow_env_prefix=False,
    )

    with pytest.raises(ValueError, match="allowlist policy"):
        runner.run(command="FOO=bar printf 'ok'")


def test_default_shell_runner_rejects_sandbox_mode_for_now() -> None:
    with pytest.raises(RuntimeError, match="not implemented"):
        DefaultShellRunner(sandbox_enabled=True)
