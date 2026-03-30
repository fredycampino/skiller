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
