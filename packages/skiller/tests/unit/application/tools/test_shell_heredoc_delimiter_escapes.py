from pathlib import Path

import pytest

from skiller.application.tools.shell.command_expander import ShellCommandExpander
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize(
    "delimiter, actual_end, mistaken_end",
    [
        ('"\\$EOF"', "$EOF", r"\$EOF"),
        ('"\\`EOF"', "`EOF", r"\`EOF"),
        ('pre"\\$EOF"', "pre$EOF", r"pre\$EOF"),
        ('"E\\$OF"', "E$OF", r"E\$OF"),
        ('"EOF\\\n"', "EOF", "EOF"),
        ('"\\\\EOF"', r"\EOF", r"\EOF"),
    ],
)
def test_rejects_double_quoted_delimiter_escapes_before_excluding_body(
    enabled: bool,
    delimiter: str,
    actual_end: str,
    mistaken_end: str,
) -> None:
    command = (
        f"cat <<{delimiter}\nliteral\n{actual_end}\nprintf HIDDEN_EXECUTION >&2\n{mistaken_end}"
    )
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=enabled,
        allowed_commands=("cat",),
    )
    with pytest.raises(ValueError, match="unsupported escape in double-quoted heredoc delimiter"):
        ShellCommandPolicy(config=config).validate_command(
            command=command,
            effective_cwd="/workspace",
            environment={},
        )


@pytest.mark.parametrize(
    "delimiter, end",
    [
        (r"\EOF", "EOF"),
        (r"\$EOF", "$EOF"),
        (r"\`EOF", "`EOF"),
        (r"'\$EOF'", r"\$EOF"),
        (r"'\`EOF'", r"\`EOF"),
        ("'pre\\'" + '"EOF"', r"pre\EOF"),
        ('"EOF"', "EOF"),
    ],
)
def test_preserves_external_escapes_and_single_quoted_backslashes(
    delimiter: str,
    end: str,
) -> None:
    command = f"cat <<{delimiter}\nliteral body\n{end}\ncat"
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    assert "literal body" not in source
    assert source.endswith("cat")


def test_escape_text_in_literal_body_does_not_trigger_delimiter_rejection() -> None:
    command = "cat <<'EOF'\ncat <<\"\\$INNER\"\nEOF"
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    assert "INNER" not in source
