from pathlib import Path

import pytest

from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.models import ShellToolRequest
from skiller.application.tools.shell.policy import ShellCommandPolicy
from skiller.application.tools.shell.process_tool import ShellProcessTool

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("enabled", [True, False])
def test_expand_paths_configuration(tmp_path: Path, enabled: bool) -> None:
    tool = ShellProcessTool()
    config = tool.to_runtime_config(raw={"expand_paths": enabled}, base_path=tmp_path)
    assert config.expand_paths is enabled


def test_expand_paths_defaults_to_true_and_requires_boolean(tmp_path: Path) -> None:
    tool = ShellProcessTool()
    assert tool.to_runtime_config(raw={}, base_path=tmp_path).expand_paths is True
    with pytest.raises(ValueError, match="expand_paths.*boolean"):
        tool.to_runtime_config(raw={"expand_paths": "false"}, base_path=tmp_path)


@pytest.mark.parametrize("enabled", [True, False])
def test_expand_paths_controls_validation_not_execution(tmp_path: Path, enabled: bool) -> None:
    tool = ShellProcessTool(shell="/bin/bash")
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool, allowed_paths=(tmp_path,), expand_paths=enabled
    )
    command = 'settings_dir="$HOME/.skiller/settings"\nconfig_file="$settings_dir/providers.json"'
    request = ShellToolRequest(
        command=command, cwd=str(tmp_path), env={"HOME": str(tmp_path), "settings_dir": ""}
    )
    result = tool.policy(config=config, request=request)
    if enabled:
        assert not result.ok
        assert "escapes allowed_paths" in result.error
        return
    assert result.ok
    assert result.request is not None
    process = tool.call(config=config, request=result.request)
    assert process.command[-1] == command


@pytest.mark.parametrize("command", ["cat /outside/file", "sudo true", "cat <<EOF\ntext\nEOF"])
def test_disabled_expansion_preserves_other_checks(tmp_path: Path, command: str) -> None:
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool, allowed_paths=(tmp_path,), expand_paths=False
    )
    policy = ShellCommandPolicy(config=config)
    with pytest.raises(ValueError):
        policy.validate_command(command=command, effective_cwd=str(tmp_path), environment={})


@pytest.mark.parametrize("enabled", [True, False])
def test_absolute_dynamic_path_is_not_mistaken_for_literal(tmp_path: Path, enabled: bool) -> None:
    workspace = tmp_path / "workspace"
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool, allowed_paths=(workspace,), expand_paths=enabled
        )
    )
    policy.validate_command(
        command=f'cat "{tmp_path}/${{TARGET}}/file.txt"',
        effective_cwd=str(workspace),
        environment={"TARGET": "workspace"},
    )


@pytest.mark.parametrize(
    "command",
    [
        "cat '/outside/${TARGET}/file'",
        r'cat "/outside/\$TARGET/file"',
        r"cat /outside/\$TARGET/file",
        "cat /outside/file '$TARGET'",
        "cat /outside/cost$",
        'cat "/outside/$/file"',
        "cat /outside/$:file",
        'cat "/outside/$/file" "$TARGET"',
    ],
)
def test_literal_paths_with_dollar_text_remain_checked(tmp_path: Path, command: str) -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool, allowed_paths=(tmp_path,), expand_paths=False
        )
    )
    with pytest.raises(ValueError, match="escapes allowed_paths"):
        policy.validate_command(command=command, effective_cwd=str(tmp_path), environment={})


@pytest.mark.parametrize(
    "reference",
    [
        "$TARGET",
        "${TARGET}",
        "$(printf workspace)",
        "$((1+1))",
        "$1",
        "$@",
        "$*",
        "$#",
        "$?",
        "$$",
        "$!",
        "$-",
        "$_",
    ],
)
def test_disabled_expansion_recognizes_shell_references(tmp_path: Path, reference: str) -> None:
    policy = ShellCommandPolicy(
        config=ShellToolRuntimeConfig(
            definition=ShellProcessTool, allowed_paths=(tmp_path,), expand_paths=False
        )
    )
    policy.validate_command(
        command=f'cat "/outside/{reference}/file"',
        effective_cwd=str(tmp_path),
        environment={},
    )


def test_disabled_expansion_still_excludes_literal_heredoc_body(tmp_path: Path) -> None:
    config = ShellToolRuntimeConfig(
        definition=ShellProcessTool, allowed_paths=(tmp_path,), expand_paths=False
    )
    policy = ShellCommandPolicy(config=config)
    policy.validate_command(
        command="cat <<'EOF'\n/outside/file\nEOF\n",
        effective_cwd=str(tmp_path),
        environment={},
    )
