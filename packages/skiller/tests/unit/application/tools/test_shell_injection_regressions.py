from pathlib import Path

import pytest

from skiller.application.tools.shell.command_expander import ShellCommandExpander
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.models import ShellToolRequest
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool

pytestmark = pytest.mark.unit


@pytest.fixture
def restricted_policy() -> ShellCommandPolicy:
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=True,
        allowed_commands=("pwd", "cat", "time", "!"),
    )
    return ShellCommandPolicy(config=config)


@pytest.mark.parametrize(
    "command",
    [
        "pwd\ncurl --version",
        "pwd & curl --version",
        "pwd |& curl --version",
        "pwd $(curl --version)",
        "pwd `curl --version`",
        "cat <(curl --version)",
        "cat >(curl --version)",
        "time curl --version",
        "! curl --version",
        "pwd # <<'pwd'\nprintf 'COMANDO_OCULTO\\n'\npwd",
        "cat <<'EOF' \\\n$(printf 'COMANDO_OCULTO')\ntexto literal\nEOF",
        ">/outside/file pwd",
        "</outside/file pwd",
        "pwd >/outside/file",
        "pwd>/outside/file",
        "cat</outside/file",
        "cat </outside/file",
        "pwd\n/outside/pwd",
        "pwd\ncat ${TMP_TEST}/file",
        "pwd\ncat $TMP_TEST/file",
    ],
)
def test_blocks_known_bypasses(restricted_policy, command: str) -> None:
    with pytest.raises(ValueError):
        restricted_policy.validate_command(
            command=command,
            effective_cwd="/workspace",
            environment={"TMP_TEST": "/outside"},
        )


@pytest.mark.parametrize(
    "command",
    [
        "cat <<'EOF'\n$(curl)\n/outside/file\nEOF\npwd",
        "cat <<'EOF' \\\n>./output\nliteral\nEOF",
        "pwd # <<'fake'\npwd",
        "pwd >./output 2>&1",
        "cat <./input",
    ],
)
def test_preserves_supported_commands(restricted_policy, command: str) -> None:
    restricted_policy.validate_command(
        command=command,
        effective_cwd="/workspace",
        environment={},
    )


def test_heredoc_preparation_preserves_continued_command() -> None:
    command = "cat <<'EOF' \\\n$(printf marker)\nliteral body\nEOF"
    source = ShellCommandExpander().without_heredoc_bodies(command=command)
    assert "$(printf marker)" in source
    assert "literal body" not in source


def test_multiline_quoted_text_does_not_declare_heredoc() -> None:
    command = "cat 'literal\n<<\"EOF\"\ntext'\npwd"
    assert ShellCommandExpander().without_heredoc_bodies(command=command) == command


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("environment", [None, {}, {"BASH_ENV": "/outside/startup"}])
def test_request_environment_policy(tmp_path, enabled, environment) -> None:
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(tmp_path,),
        allowlist_enabled=enabled,
        allowed_commands=("pwd",),
    )
    request = ShellToolRequest(command="pwd", cwd=None, env=environment, timeout=None)
    result = ShellProcessTool().policy(config=config, request=request)
    assert result.ok == (not enabled or not environment)


@pytest.mark.parametrize("command", ["pwd $(date)", "pwd & pwd", "(pwd)", "time pwd"])
def test_disabled_allowlist_does_not_enable_new_syntax_restrictions(command) -> None:
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(Path("/workspace"),),
        allowlist_enabled=False,
    )
    ShellCommandPolicy(config=config).validate_command(
        command=command,
        effective_cwd="/workspace",
        environment={},
    )
