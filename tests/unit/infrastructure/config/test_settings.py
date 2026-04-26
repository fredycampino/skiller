from __future__ import annotations

import json

import pytest

from skiller.infrastructure.config import settings as settings_module

pytestmark = pytest.mark.unit

_SETTINGS_ENV_NAMES = (
    "AGENT_CONFIG_FILE",
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


def test_get_settings_loads_explicit_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    secret_path = tmp_path / "minimax-key"
    secret_path.write_text("test-key\n", encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "runtime": {
                    "db_path": "/tmp/skiller.db",
                    "log_level": "DEBUG",
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
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))

    settings = settings_module.get_settings()

    assert settings.db_path == "/tmp/skiller.db"
    assert settings.log_level == "DEBUG"
    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "test-key"
    assert settings.minimax_model == "MiniMax-M2.5"
    assert settings.minimax_timeout_seconds == 13.5
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
    (config_dir / "config.json").write_text(
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


def test_get_settings_environment_overrides_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-chat",
                    "providers": {"fake-chat": {"type": "fake", "model": "fake-model"}},
                },
                "webhooks": {"port": 9002},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "minimax")
    monkeypatch.setenv("AGENT_MINIMAX_API_KEY", "env-key")
    monkeypatch.setenv("AGENT_WEBHOOKS_PORT", "9010")

    settings = settings_module.get_settings()

    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "env-key"
    assert settings.webhooks_port == 9010


def test_get_settings_loads_secret_from_provider_env_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
    config_path.write_text(
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
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("TEST_MINIMAX_KEY", "env-ref-key")

    settings = settings_module.get_settings()

    assert settings.minimax_api_key == "env-ref-key"


def test_get_settings_raises_when_explicit_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="AGENT_CONFIG_FILE does not exist"):
        settings_module.get_settings()


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in _SETTINGS_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
