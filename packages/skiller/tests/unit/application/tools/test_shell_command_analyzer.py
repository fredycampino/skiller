import pytest

from skiller.application.tools.shell.command_analyzer import ShellCommandAnalyzer

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("separator", ["\n", ";", "|", "&&", "||"])
def test_identifies_every_executable(separator: str) -> None:
    analysis = ShellCommandAnalyzer().analyze(f"pwd {separator} curl --version")
    assert [segment.executable for segment in analysis.segments] == ["pwd", "curl"]


@pytest.mark.parametrize(
    "command",
    [
        "pwd & curl --version",
        "pwd |& curl --version",
        "pwd &>file",
        "pwd &>>file",
        "pwd $(curl --version)",
        "pwd `curl --version`",
        "cat <(curl --version)",
        "cat >(curl --version)",
        'pwd "$(curl --version)"',
        "(pwd)",
        "{ pwd; }",
        "time curl",
        "! curl",
        "coproc curl",
        "if pwd; then curl; fi",
        "for x in a; do curl; done",
        "f() { curl; }",
        "$COMMAND",
        "p${X}d",
        '"p${X}d"',
        "./bin/*",
        "~/bin/pwd",
        "p{w,x}d",
        ">/outside/file pwd",
        "2>/outside/file pwd",
        "X=y </outside/file pwd",
        "pwd >&file",
        "pwd <&$FD",
        "pwd <<<hello",
    ],
)
def test_rejects_unsupported_execution(command: str) -> None:
    with pytest.raises(ValueError):
        ShellCommandAnalyzer().analyze(command)


@pytest.mark.parametrize(
    "command",
    [
        "pwd",
        "'p'wd",
        "p\\wd",
        "p\\\nwd",
        '"pwd"',
        "pwd '$(curl)'",
        'pwd "\\$(curl)"',
        "pwd '`curl`'",
        "pwd '; & | $(curl)'",
        "pwd # $(curl)\npwd",
        "pwd >./output 2>&1",
        "pwd >>./output 2>&-",
        "pwd <./input",
    ],
)
def test_accepts_literals_and_supported_redirections(command: str) -> None:
    analysis = ShellCommandAnalyzer().analyze(command)
    assert all(segment.executable == "pwd" for segment in analysis.segments)


def test_reports_environment_prefix_without_deciding_permission() -> None:
    analysis = ShellCommandAnalyzer().analyze("MODE=test pwd")
    assert analysis.segments[0].has_env_prefix
