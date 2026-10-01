from pathlib import Path

import pytest

from skiller.application.tools.shell.command_expander import ShellCommandExpander
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize(
    "delimiter, shell_end, mistaken_end",
    [
        ("$'EOF'", "EOF", "$EOF"),
        ('$"EOF"', "EOF", "$EOF"),
        ("pre$'EOF'", "preEOF", "pre$EOF"),
        ('pre$"EOF"', "preEOF", "pre$EOF"),
        ("$'E'\"OF\"", "EOF", "$EOF"),
        ("$\\\n'EOF'", "EOF", "$EOF"),
        ('$\\\n"EOF"', "EOF", "$EOF"),
    ],
)
def test_rejects_special_quotes_before_excluding_heredoc_body(
    enabled: bool,
    delimiter: str,
    shell_end: str,
    mistaken_end: str,
) -> None:
    command = (
        f"cat <<{delimiter}\nliteral\n{shell_end}\nprintf HIDDEN_EXECUTION >&2\n{mistaken_end}"
    )
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=enabled,
        allowed_commands=("cat",),
    )
    with pytest.raises(ValueError, match="unsupported dollar-quoted heredoc delimiter"):
        ShellCommandPolicy(config=config).validate_command(
            command=command,
            effective_cwd="/workspace",
            environment={},
        )


@pytest.mark.parametrize(
    "delimiter, end",
    [
        ("'EOF'", "EOF"),
        ('"EOF"', "EOF"),
        ("\\EOF", "EOF"),
        ("'E'\"OF\"", "EOF"),
        ("\\$'EOF'", "$EOF"),
        ("'$'\"EOF\"", "$EOF"),
        ("'$\"EOF\"'", '$"EOF"'),
        ("\"$'EOF'\"", "$'EOF'"),
    ],
)
def test_preserves_ordinary_quotes_and_literal_dollar_quote_mentions(
    delimiter: str,
    end: str,
) -> None:
    command = f"cat <<{delimiter}\nliteral\n{end}\npwd"
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    assert "literal" not in source
    assert source.endswith("pwd")


def test_special_quote_text_inside_literal_body_is_not_a_declaration() -> None:
    command = "cat <<'EOF'\ncat <<$'INNER'\nEOF"
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    assert "INNER" not in source
