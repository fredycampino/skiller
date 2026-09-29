import pytest

from skiller.application.tools.shell.command_expander import ShellCommandExpander

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("command", "expected"),
    (
        ("cat $ROOT/file", "cat workspace/file"),
        ("cat ${ROOT}/file", "cat workspace/file"),
        ("cat ${ROOT}_backup/file", "cat workspace_backup/file"),
        ("cat $ROOT/$NAME", "cat workspace/report.txt"),
    ),
)
def test_shell_command_expander_expands_variable_references(
    command: str,
    expected: str,
) -> None:
    expander = ShellCommandExpander()

    result = expander.expand(
        command=command,
        environment={"ROOT": "workspace", "NAME": "report.txt"},
    )

    assert result == expected


@pytest.mark.parametrize(
    "command",
    (
        "cat '$ROOT/file'",
        "cat '${ROOT}/file'",
        r"cat \$ROOT/file",
        r"cat \${ROOT}/file",
    ),
)
def test_shell_command_expander_preserves_literal_references(
    command: str,
) -> None:
    expander = ShellCommandExpander()

    result = expander.expand(
        command=command,
        environment={"ROOT": "outside"},
    )

    assert result == command


def test_shell_command_expander_preserves_double_quoted_value() -> None:
    expander = ShellCommandExpander()

    result = expander.expand(
        command='cat "$ROOT/file"',
        environment={"ROOT": "workspace root"},
    )

    assert result == 'cat "workspace root/file"'


def test_shell_command_expander_preserves_unquoted_field_splitting() -> None:
    expander = ShellCommandExpander()

    result = expander.expand(
        command="cat $TARGETS/file",
        environment={"TARGETS": "first second"},
    )

    assert result == "cat first second/file"


@pytest.mark.parametrize(
    ("command", "expected"),
    (
        ("cat $MISSING/file", "cat ''/file"),
        ("cat ${MISSING}/file", "cat ''/file"),
        ('cat "$MISSING/file"', 'cat "/file"'),
    ),
)
def test_shell_command_expander_uses_empty_missing_variables(
    command: str,
    expected: str,
) -> None:
    expander = ShellCommandExpander()

    result = expander.expand(command=command, environment={})

    assert result == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    (
        ("cat ~", "cat /home/tester"),
        ("cat ~/file", "cat /home/tester/file"),
        ("cat ./first && cat ~/second", "cat ./first && cat /home/tester/second"),
        ("ROOT=~/workspace command", "ROOT=/home/tester/workspace command"),
    ),
)
def test_shell_command_expander_expands_supported_tilde_references(
    command: str,
    expected: str,
) -> None:
    expander = ShellCommandExpander()

    result = expander.expand(command=command, environment={"HOME": "/home/tester"})

    assert result == expected


@pytest.mark.parametrize(
    "command",
    (
        "cat '~/file'",
        'cat "~/file"',
        r"cat \~/file",
        "cat prefix~/file",
    ),
)
def test_shell_command_expander_preserves_literal_tilde_references(command: str) -> None:
    expander = ShellCommandExpander()

    result = expander.expand(command=command, environment={"HOME": "/outside"})

    assert result == command


@pytest.mark.parametrize("reference", ("~+", "~-", "~alice", "~alice/file"))
def test_shell_command_expander_rejects_unsupported_tilde_references(
    reference: str,
) -> None:
    expander = ShellCommandExpander()

    with pytest.raises(
        ValueError,
        match="shell command uses unsupported tilde expansion",
    ):
        expander.expand(command=f"cat {reference}", environment={"HOME": "/home/tester"})


def test_shell_command_expander_requires_home_for_tilde_expansion() -> None:
    expander = ShellCommandExpander()

    with pytest.raises(ValueError, match="HOME is not set"):
        expander.expand(command="cat ~/file", environment={})


def test_shell_command_expander_does_not_expand_tilde_from_variable_value() -> None:
    expander = ShellCommandExpander()

    result = expander.expand(
        command="cat $TARGET",
        environment={"HOME": "/home/tester", "TARGET": "~/file"},
    )

    assert result == "cat '~/file'"


@pytest.mark.parametrize(
    "declaration",
    (
        "cat <<'EOF'",
        'cat <<"EOF"',
        r"cat <<\EOF",
    ),
)
def test_shell_command_expander_ignores_quoted_heredoc_bodies(
    declaration: str,
) -> None:
    expander = ShellCommandExpander()
    command = f"{declaration}\n~/file\n$ROOT/file\n${{ROOT}}/file\nEOF"

    result = expander.expand(
        command=command,
        environment={"ROOT": "/outside"},
    )

    assert result == f"{declaration}\n\n\n\n"


def test_shell_command_expander_ignores_tab_stripped_heredoc_body() -> None:
    expander = ShellCommandExpander()
    command = "cat <<-'EOF'\n\t~/file\n\tEOF"

    result = expander.expand(command=command, environment={})

    assert result == "cat <<-'EOF'\n\n"


def test_shell_command_expander_ignores_multiple_heredoc_bodies() -> None:
    expander = ShellCommandExpander()
    command = "cat <<'FIRST' <<'SECOND'\n~/first\nFIRST\n$ROOT/second\nSECOND"

    result = expander.expand(command=command, environment={"ROOT": "/outside"})

    assert result == "cat <<'FIRST' <<'SECOND'\n\n\n\n"


def test_shell_command_expander_resumes_after_heredoc() -> None:
    expander = ShellCommandExpander()
    command = "cat <<'EOF'\n~/literal\nEOF\ncat $ROOT/file"

    result = expander.expand(
        command=command,
        environment={"HOME": "/home/tester", "ROOT": "/workspace"},
    )

    assert result == "cat <<'EOF'\n\n\ncat /workspace/file"


def test_shell_command_expander_rejects_unterminated_heredoc() -> None:
    expander = ShellCommandExpander()

    with pytest.raises(ValueError, match="shell command has unterminated heredoc: EOF"):
        expander.expand(command="cat <<'EOF'\ncontent", environment={})


def test_shell_command_expander_rejects_unquoted_heredoc() -> None:
    expander = ShellCommandExpander()
    command = "cat <<EOF\n~/file\nEOF"

    with pytest.raises(
        ValueError,
        match="unsupported unquoted heredoc delimiter: EOF",
    ):
        expander.expand(command=command, environment={"HOME": "/outside"})
