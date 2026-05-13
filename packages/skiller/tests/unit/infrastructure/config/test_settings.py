from __future__ import annotations

import json

import pytest

from skiller.infrastructure.config import settings as settings_module

pytestmark = pytest.mark.unit

_SETTINGS_ENV_NAMES = (
    "AGENT_CONFIG_FILE",
    "AGENT_AGENT_CONFIG_FILE",
    "AGENT_DB_PATH",
    "AGENT_LLM_PROVIDER",
    "AGENT_FAKE_LLM_RESPONSE_JSON",
    "AGENT_FAKE_LLM_MODEL",
    "AGENT_MINIMAX_API_KEY",
    "AGENT_MINIMAX_BASE_URL",
    "AGENT_MINIMAX_MODEL",
    "AGENT_MINIMAX_TIMEOUT_SECONDS",
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
    "AGENT_EVENT_OUTPUT_PII_ENABLED",
    "AGENT_EVENT_OUTPUT_SECRETS_ENABLED",
    "AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS",
    "AGENT_EVENT_OUTPUT_MAX_JSON_CHARS",
    "AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS",
    "AGENT_LOOP_MAX_TURNS",
    "AGENT_LOOP_MAX_TOOL_CALLS",
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
    assert settings.llm_provider == "null"
    assert settings.whatsapp_bridge_send_timeout_seconds == 10.0
    assert settings.agent_shell_allowlist_enabled is False
    assert settings.agent_shell_allowlist_workspace == ""
    assert settings.agent_shell_allowlist_allow_env_prefix is True
    assert settings.agent_shell_allowlist_allowed_commands == ()
    assert settings.agent_shell_sandbox_enabled is False
    assert settings.agent_event_output_truncate_enabled is True
    assert settings.agent_event_output_pii_enabled is True
    assert settings.agent_event_output_secrets_enabled is True
    assert settings.agent_event_output_max_text_chars == 600
    assert settings.agent_event_output_max_json_chars == 4000
    assert settings.agent_event_output_max_array_items == 20
    assert settings.agent_loop_max_turns == 10
    assert settings.agent_loop_max_tool_calls == 5


def test_get_settings_loads_explicit_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    secret_path = tmp_path / "minimax-key"
    secret_path.write_text("test-key\n", encoding="utf-8")
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
    agent_config_path.write_text(
        json.dumps(
            {
                "agent": {
                    "loop": {
                        "max_turns": 12,
                        "max_tool_calls": 6,
                    }
                },
                "llm": {
                    "default_provider": "minimax-fast",
                    "providers": {
                        "minimax-fast": {
                            "type": "minimax",
                            "api_key_file": str(secret_path),
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 13.5,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))

    settings = settings_module.get_settings()

    assert settings.db_path == "/tmp/skiller.db"
    assert settings.log_level == "DEBUG"
    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "test-key"
    assert settings.minimax_model == "MiniMax-M2.5"
    assert settings.minimax_timeout_seconds == 13.5
    assert settings.agent_loop_max_turns == 12
    assert settings.agent_loop_max_tool_calls == 6
    assert settings.webhooks_host == "0.0.0.0"
    assert settings.webhooks_port == 9002
    assert settings.whatsapp_bridge_host == "0.0.0.0"
    assert settings.whatsapp_bridge_port == 9003
    assert settings.whatsapp_bridge_send_timeout_seconds == 14.5


def test_get_settings_loads_global_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    home = tmp_path / "home"
    config_dir = home / ".skiller" / "settings"
    config_dir.mkdir(parents=True)
    (config_dir / "agent.json").write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-chat",
                    "providers": {
                        "fake-chat": {
                            "type": "fake",
                            "model": "global-model",
                            "response_json": {"reply": "hola"},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(home))

    settings = settings_module.get_settings()

    assert settings.llm_provider == "fake"
    assert settings.fake_llm_model == "global-model"
    assert settings.fake_llm_response_json == '{"reply": "hola"}'


def test_get_settings_prefers_client_type_over_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    agent_config_path = tmp_path / "agent.json"
    agent_config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-main",
                    "providers": {
                        "fake-main": {
                            "client_type": "fake",
                            "type": "minimax",
                            "model": "fake-model-v2",
                            "response_json": {"status": "ok"},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))

    settings = settings_module.get_settings()

    assert settings.llm_provider == "fake"
    assert settings.fake_llm_model == "fake-model-v2"
    assert settings.fake_llm_response_json == '{"status": "ok"}'


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
                        },
                        "pii": {"enabled": False},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "agent.json").write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-chat",
                    "providers": {
                        "fake-chat": {
                            "type": "fake",
                            "model": "global-model",
                            "response_json": {"reply": "hola"},
                        }
                    },
                },
                "event_output": {
                    "truncate": {
                        "max_json_chars": 9000,
                        "max_array_items": 33,
                    },
                    "secrets": {"enabled": False},
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
    assert settings.llm_provider == "fake"
    assert settings.fake_llm_model == "global-model"
    assert settings.fake_llm_response_json == '{"reply": "hola"}'
    assert settings.agent_shell_allowlist_enabled is True
    assert settings.agent_shell_allowlist_workspace == "/tmp/skiller-workspace"
    assert settings.agent_shell_allowlist_allow_env_prefix is False
    assert settings.agent_shell_allowlist_allowed_commands == ("git", "rg")
    assert settings.agent_event_output_truncate_enabled is True
    assert settings.agent_event_output_pii_enabled is False
    assert settings.agent_event_output_secrets_enabled is False
    assert settings.agent_event_output_max_text_chars == 700
    assert settings.agent_event_output_max_json_chars == 9000
    assert settings.agent_event_output_max_array_items == 33


def test_get_settings_environment_overrides_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    agent_config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "webhooks": {"port": 9002},
            }
        ),
        encoding="utf-8",
    )
    agent_config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-chat",
                    "providers": {"fake-chat": {"type": "fake", "model": "fake-model"}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "minimax")
    monkeypatch.setenv("AGENT_MINIMAX_API_KEY", "env-key")
    monkeypatch.setenv("AGENT_WEBHOOKS_PORT", "9010")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ENABLED", "true")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_WORKSPACE", "~/sandbox/ws")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX", "false")
    monkeypatch.setenv("AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS", "git, rg,pytest")
    monkeypatch.setenv("AGENT_SHELL_SANDBOX_ENABLED", "false")
    monkeypatch.setenv("AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED", "false")
    monkeypatch.setenv("AGENT_EVENT_OUTPUT_PII_ENABLED", "0")
    monkeypatch.setenv("AGENT_EVENT_OUTPUT_SECRETS_ENABLED", "off")
    monkeypatch.setenv("AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS", "1234")

    settings = settings_module.get_settings()

    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "env-key"
    assert settings.webhooks_port == 9010
    assert settings.agent_shell_allowlist_enabled is True
    assert settings.agent_shell_allowlist_workspace.endswith("/sandbox/ws")
    assert settings.agent_shell_allowlist_allow_env_prefix is False
    assert settings.agent_shell_allowlist_allowed_commands == ("git", "rg", "pytest")
    assert settings.agent_shell_sandbox_enabled is False
    assert settings.agent_event_output_truncate_enabled is False
    assert settings.agent_event_output_pii_enabled is False
    assert settings.agent_event_output_secrets_enabled is False
    assert settings.agent_event_output_max_text_chars == 1234


def test_get_settings_loads_secret_from_provider_env_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    agent_config_path = tmp_path / "agent.json"
    agent_config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax",
                    "providers": {
                        "minimax": {
                            "type": "minimax",
                            "api_key_env": "TEST_MINIMAX_KEY",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_AGENT_CONFIG_FILE", str(agent_config_path))
    monkeypatch.setenv("TEST_MINIMAX_KEY", "env-ref-key")

    settings = settings_module.get_settings()

    assert settings.minimax_api_key == "env-ref-key"


def test_get_settings_ignores_llm_config_from_main_config_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-chat",
                    "providers": {"fake-chat": {"type": "fake", "model": "from-config"}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))

    settings = settings_module.get_settings()

    assert settings.llm_provider == "null"


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
                    "secrets": {"enabled": False},
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

    assert settings.agent_event_output_secrets_enabled is False
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
