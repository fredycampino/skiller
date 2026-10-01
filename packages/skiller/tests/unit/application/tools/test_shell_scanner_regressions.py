import subprocess
import sys
from pathlib import Path

import pytest

from skiller.application.tools.shell.command_analyzer import ShellCommandAnalyzer
from skiller.application.tools.shell.command_expander import ShellCommandExpander
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool
from skiller.application.tools.shell.source import remove_shell_line_continuations

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("space", ["\u00a0", "\v", "\f"])
def test_policy_terminates_on_non_shell_whitespace(space: str) -> None:
    # A subprocess timeout bounds the validation itself, not command execution.
    script = f"""
from pathlib import Path
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool
config = ShellToolRuntimeConfig(
    definition=ShellProcessTool, allowed_paths=(Path('/workspace'),),
    allowlist_enabled=True, allowed_commands=('pwd',),
)
try:
    ShellCommandPolicy(config=config).validate_command(
        command={("pwd" + space + "argument")!r},
        effective_cwd='/workspace', environment={{}},
    )
except ValueError as error:
    assert 'not in the shell allowlist' in str(error)
else:
    raise AssertionError('The whitespace is part of the executable name')
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=5)


@pytest.mark.parametrize(
    "command",
    [
        'pwd "$\\\n(printf MARCADOR >&2)"',
        'pwd "$\\\n\\\n(printf MARCADOR >&2)"',
        "pwd $\\\n(printf MARCADOR)",
        "pwd <\\\n(printf MARCADOR)",
        "pwd >\\\n(printf MARCADOR)",
        "pwd &\\\n pwd",
        "pwd |\\\n& pwd",
    ],
)
def test_policy_rejects_execution_hidden_by_continuations(command: str) -> None:
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=True,
        allowed_commands=("pwd",),
    )
    with pytest.raises(ValueError, match="unsupported"):
        ShellCommandPolicy(config=config).validate_command(
            command=command,
            effective_cwd="/workspace",
            environment={},
        )


@pytest.mark.parametrize(
    "source, expected",
    [
        ('pwd "$\\\n(printf marker)"', 'pwd "$(printf marker)"'),
        ("p\\\nwd", "pwd"),
        ("pwd &\\\n& pwd", "pwd && pwd"),
        ("pwd '$\\\n(marker)'", "pwd '$\\\n(marker)'"),
        ('pwd "\\\\\ntext"', 'pwd "\\\\\ntext"'),
        ("pwd # comment \\\nnext", "pwd # comment \\\nnext"),
    ],
)
def test_contextual_line_continuations(source: str, expected: str) -> None:
    assert remove_shell_line_continuations(source) == expected


def test_literal_heredoc_body_is_removed_before_continuation_analysis() -> None:
    command = "cat <<'EOF'\n$\\\n(printf marker)\nEOF"
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    assert ShellCommandAnalyzer().analyze(source).segments[0].executable == "cat"


@pytest.mark.parametrize("enabled", [False, True])
def test_here_string_preserves_unrestricted_mode(enabled: bool) -> None:
    command = "cat <<< 'literal'"
    assert ShellCommandExpander().without_heredoc_bodies(command=command) == command
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=enabled,
        allowed_commands=("cat",),
    )
    policy = ShellCommandPolicy(config=config)
    if enabled:
        with pytest.raises(ValueError, match="unsupported"):
            policy.validate_command(command=command, effective_cwd="/workspace", environment={})
        return
    policy.validate_command(command=command, effective_cwd="/workspace", environment={})
