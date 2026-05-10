from __future__ import annotations

import json

import pytest
from skiller.infrastructure.tools.shell.config import resolve_shell_settings

pytestmark = pytest.mark.unit

_SHELL_ENV_NAMES = (
    "AGENT_SHELL_ALLOWLIST_ENABLED",
    "AGENT_SHELL_ALLOWLIST_WORKSPACE",
    "AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX",
    "AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS",
    "AGENT_SHELL_SANDBOX_ENABLED",
)


def test_resolve_shell_settings_reads_root_shell_policy(tmp_path, monkeypatch) -> None:
    _clear_shell_env(monkeypatch)
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "shell": {
                    "policy": {
                        "allowlist": {
                            "enabled": True,
                            "workspace": "/tmp/workspace",
                            "allow_env_prefix": False,
                            "allowed_commands": ["git", "rg"],
                        },
                        "sandbox": {"enabled": False},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    settings = resolve_shell_settings(agent_path)

    assert settings.allowlist_enabled is True
    assert settings.workspace == "/tmp/workspace"
    assert settings.allow_env_prefix is False
    assert settings.allowed_commands == ("git", "rg")
    assert settings.sandbox_enabled is False


def test_resolve_shell_settings_env_overrides_file(tmp_path, monkeypatch) -> None:
    _clear_shell_env(monkeypatch)
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "shell": {
                    "policy": {
                        "allowlist": {
                            "enabled": False,
                            "workspace": "/tmp/base",
                            "allow_env_prefix": True,
                            "allowed_commands": ["git"],
                        },
                        "sandbox": {"enabled": False},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ENABLED", "true")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_WORKSPACE", "~/sandbox/ws")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX", "false")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS", "git, rg,pytest")
    monkeypatch.setenv("AGENT_SHELL_SANDBOX_ENABLED", "true")

    settings = resolve_shell_settings(agent_path)

    assert settings.allowlist_enabled is True
    assert settings.workspace.endswith("/sandbox/ws")
    assert settings.allow_env_prefix is False
    assert settings.allowed_commands == ("git", "rg", "pytest")
    assert settings.sandbox_enabled is True


def test_resolve_shell_settings_raises_on_invalid_shape(tmp_path, monkeypatch) -> None:
    _clear_shell_env(monkeypatch)
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(json.dumps({"shell": "invalid"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="field 'shell' must be a JSON object"):
        resolve_shell_settings(agent_path)


def test_resolve_shell_settings_uses_defaults_when_file_missing(tmp_path, monkeypatch) -> None:
    _clear_shell_env(monkeypatch)
    missing_path = tmp_path / "missing-agent.json"

    settings = resolve_shell_settings(missing_path)

    assert settings.allowlist_enabled is False
    assert settings.workspace == ""
    assert settings.allow_env_prefix is True
    assert settings.allowed_commands == ()
    assert settings.sandbox_enabled is False


def _clear_shell_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in _SHELL_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
