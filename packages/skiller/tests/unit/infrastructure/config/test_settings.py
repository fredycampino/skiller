from __future__ import annotations

import json

import pytest

from skiller.infrastructure.config import settings as settings_module

pytestmark = pytest.mark.unit

_SETTINGS_ENV_NAMES = (
    "AGENT_CONFIG_FILE",
    "AGENT_AGENT_CONFIG_FILE",
    "AGENT_DB_PATH",
    "AGENT_LOG_LEVEL",
    "AGENT_WEBHOOKS_HOST",
    "AGENT_WEBHOOKS_PORT",
    "AGENT_WHATSAPP_BRIDGE_HOST",
    "AGENT_WHATSAPP_BRIDGE_PORT",
    "AGENT_WHATSAPP_BRIDGE_SEND_TIMEOUT_SECONDS",
    "AGENT_SHELL_ALLOWLIST_ENABLED",
    "AGENT_SHELL_ALLOWLIST_WORKSPACE",
    "AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX",
    "AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS",
    "AGENT_SHELL_SANDBOX_ENABLED",
    "AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED",
    "AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS",
    "AGENT_EVENT_OUTPUT_MAX_JSON_CHARS",
    "AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS",
)


def test_get_settings_uses_defaults_when_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    settings = settings_module.get_settings()

    assert settings.db_path == "./runtime.db"
    assert settings.whatsapp_bridge_send_timeout_seconds == 10.0
    assert settings.agent_shell_allowlist_enabled is False
    assert settings.agent_shell_allowlist_workspace == ""
    assert settings.agent_shell_allowlist_allow_env_prefix is True
    assert settings.agent_shell_allowlist_allowed_commands == ()
    assert settings.agent_shell_sandbox_enabled is False
    assert settings.agent_event_output_truncate_enabled is True
    assert settings.agent_event_output_max_text_chars == 600
    assert settings.agent_event_output_max_json_chars == 4000
    assert settings.agent_event_output_max_array_items == 20


def test_get_settings_loads_explicit_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    agent_config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "runtime": {
                    "db_path": "/tmp/skiller.db",
                    "log_level": "DEBUG",
                },
                "webhooks": {
                    "host": "0.0.0.0",
                    "port": 9002,
                },
                "whatsapp": {
                    "bridge": {
                        "host": "0.0.0.0",
                        "port": 9003,
                        "send_timeout_seconds": 14.5,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    agent_config_path.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))

    settings = settings_module.get_settings()

    assert settings.db_path == "/tmp/skiller.db"
    assert settings.log_level == "DEBUG"
    assert settings.webhooks_host == "0.0.0.0"
    assert settings.webhooks_port == 9002
    assert settings.whatsapp_bridge_host == "0.0.0.0"
    assert settings.whatsapp_bridge_port == 9003
    assert settings.whatsapp_bridge_send_timeout_seconds == 14.5


def test_get_settings_uses_local_agent_json_before_global(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    home = tmp_path / "home"
    global_dir = home / ".skiller" / "settings"
    global_dir.mkdir(parents=True)
    (global_dir / "agent.json").write_text(
        json.dumps(
            {
                "event_output": {
                    "truncate": {
                        "max_text_chars": 100,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "agent.json").write_text(
        json.dumps(
            {
                "event_output": {
                    "truncate": {
                        "max_text_chars": 900,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    settings = settings_module.get_settings()

    assert settings.agent_config_path == "agent.json"
    assert settings.agent_event_output_max_text_chars == 900


def test_get_settings_uses_explicit_agent_config_before_local(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    local_path = tmp_path / "agent.json"
    explicit_path = tmp_path / "explicit-agent.json"
    local_path.write_text(
        json.dumps(
            {
                "event_output": {
                    "truncate": {
                        "max_text_chars": 100,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    explicit_path.write_text(
        json.dumps(
            {
                "event_output": {
                    "truncate": {
                        "max_text_chars": 700,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(explicit_path))

    settings = settings_module.get_settings()

    assert settings.agent_config_path == str(explicit_path)
    assert settings.agent_event_output_max_text_chars == 700


def test_get_settings_loads_agent_config_file_and_merges_with_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    home = tmp_path / "home"
    config_dir = home / ".skiller" / "settings"
    config_dir.mkdir(parents=True)

    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "runtime": {
                    "db_path": "/tmp/skiller.db",
                },
                "agent": {
                    "event_output": {
                        "truncate": {
                            "enabled": True,
                            "max_text_chars": 700,
                            "max_json_chars": 5000,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "agent.json").write_text(
        json.dumps(
            {
                "event_output": {
                    "truncate": {
                        "max_json_chars": 9000,
                        "max_array_items": 33,
                    }
                },
                "shell": {
                    "policy": {
                        "allowlist": {
                            "enabled": True,
                            "workspace": "/tmp/skiller-workspace",
                            "allow_env_prefix": False,
                            "allowed_commands": ["git", "rg"],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    settings = settings_module.get_settings()

    assert settings.db_path == "/tmp/skiller.db"
    assert settings.agent_shell_allowlist_enabled is True
    assert settings.agent_shell_allowlist_workspace == "/tmp/skiller-workspace"
    assert settings.agent_shell_allowlist_allow_env_prefix is False
    assert settings.agent_shell_allowlist_allowed_commands == ("git", "rg")
    assert settings.agent_event_output_truncate_enabled is True
    assert settings.agent_event_output_max_text_chars == 700
    assert settings.agent_event_output_max_json_chars == 9000
    assert settings.agent_event_output_max_array_items == 33


def test_get_settings_environment_overrides_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "webhooks": {"port": 9002},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_WEBHOOKS_PORT", "9010")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ENABLED", "true")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_WORKSPACE", "~/sandbox/ws")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX", "false")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS", "git, rg,pytest")
    monkeypatch.setenv("AGENT_SHELL_SANDBOX_ENABLED", "false")
    monkeypatch.setenv("AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED", "false")
    monkeypatch.setenv("AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS", "1234")

    settings = settings_module.get_settings()

    assert settings.webhooks_port == 9010
    assert settings.agent_shell_allowlist_enabled is True
    assert settings.agent_shell_allowlist_workspace.endswith("/sandbox/ws")
    assert settings.agent_shell_allowlist_allow_env_prefix is False
    assert settings.agent_shell_allowlist_allowed_commands == ("git", "rg", "pytest")
    assert settings.agent_shell_sandbox_enabled is False
    assert settings.agent_event_output_truncate_enabled is False
    assert settings.agent_event_output_max_text_chars == 1234


def test_get_settings_ignores_shell_config_from_main_config_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "shell": {
                    "policy": {
                        "allowlist": {
                            "enabled": True,
                            "workspace": "/tmp/from-config",
                            "allowed_commands": ["git"],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))

    settings = settings_module.get_settings()

    assert settings.agent_shell_allowlist_enabled is False
    assert settings.agent_shell_allowlist_workspace == ""
    assert settings.agent_shell_allowlist_allowed_commands == ()


def test_get_settings_merges_root_and_agent_event_output_blocks_in_agent_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    agent_config_path = tmp_path / "agent.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")
    agent_config_path.write_text(
        json.dumps(
            {
                "event_output": {
                    "truncate": {"max_json_chars": 7000},
                },
                "agent": {
                    "event_output": {"truncate": {"max_json_chars": 9100}},
                },
                "shell": {
                    "policy": {
                        "allowlist": {
                            "enabled": True,
                            "allowed_commands": ["git"],
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))

    settings = settings_module.get_settings()

    assert settings.agent_event_output_max_json_chars == 9100
    assert settings.agent_shell_allowlist_enabled is True
    assert settings.agent_shell_allowlist_allowed_commands == ("git",)


def test_get_settings_raises_when_agent_field_is_not_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    agent_config_path = tmp_path / "agent.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")
    agent_config_path.write_text(json.dumps({"agent": "invalid"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))

    with pytest.raises(RuntimeError, match="field 'agent' must be a JSON object"):
        settings_module.get_settings()


def test_get_settings_raises_when_explicit_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="AGENT_CONFIG_FILE does not exist"):
        settings_module.get_settings()


def test_get_settings_raises_when_explicit_agent_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(tmp_path / "missing-agent.json"))

    with pytest.raises(RuntimeError, match="AGENT_AGENT_CONFIG_FILE does not exist"):
        settings_module.get_settings()


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in _SETTINGS_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
