import subprocess
from pathlib import Path

import pytest

from skiller.application.tools.shell.command_analyzer import ShellCommandAnalyzer
from skiller.application.tools.shell.command_expander import ShellCommandExpander

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("shell", ["/bin/bash", "/bin/sh"])
@pytest.mark.parametrize(
    "command, expected",
    [
        ("printf first; printf second", "firstsecond"),
        ("printf first\nprintf second", "firstsecond"),
        ("printf first && printf second", "firstsecond"),
        ("printf first || printf second", "first"),
        ("printf first | cat", "first"),
        ("cat <<'EOF' \\\n>./output\nliteral\nEOF\ncat ./output", "literal\n"),
        ("printf first # <<'fake'\nprintf second", "firstsecond"),
    ],
)
def test_supported_syntax_matches_shell(shell, command, expected, tmp_path) -> None:
    if not Path(shell).exists():
        pytest.skip(f"{shell} is unavailable")
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    analysis = ShellCommandAnalyzer().analyze(source)
    assert {segment.executable for segment in analysis.segments} <= {"printf", "cat"}
    result = subprocess.run(
        [shell, "-c", command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert result.stdout == expected
