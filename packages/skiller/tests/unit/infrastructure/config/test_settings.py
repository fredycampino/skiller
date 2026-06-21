from __future__ import annotations

import json

import pytest

from skiller.infrastructure.config import settings as settings_module

pytestmark = pytest.mark.unit

_SETTINGS_ENV_NAMES = (
    "AGENT_CONFIG_FILE",
    "AGENT_DB_PATH",
    "AGENT_LOG_LEVEL",
    "AGENT_WEBHOOKS_HOST",
    "AGENT_WEBHOOKS_PORT",
)


def test_get_settings_uses_runtime_db_default_when_no_env_file_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    settings = settings_module.get_settings()

    assert settings.db_path == "./runtime.db"


def test_get_settings_loads_development_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / ".env.development").write_text(
        "AGENT_DB_PATH=dev-runtime.db\n",
        encoding="utf-8",
    )

    settings = settings_module.get_settings()

    assert settings.db_path == "dev-runtime.db"


def test_get_settings_loads_explicit_structured_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    config_path = tmp_path / "config.json"
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
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_path))

    settings = settings_module.get_settings()

    assert settings.db_path == "/tmp/skiller.db"
    assert settings.log_level == "DEBUG"
    assert settings.webhooks_host == "0.0.0.0"
    assert settings.webhooks_port == 9002


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

    settings = settings_module.get_settings()

    assert settings.webhooks_port == 9010


def test_get_settings_environment_overrides_development_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_DB_PATH", "real-env.db")
    (tmp_path / ".env.development").write_text(
        "AGENT_DB_PATH=dev-runtime.db\n",
        encoding="utf-8",
    )

    settings = settings_module.get_settings()

    assert settings.db_path == "real-env.db"


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
