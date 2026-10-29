from __future__ import annotations

import json
from pathlib import Path

import pytest

from skiller.infrastructure.config import settings as settings_module
from skiller.infrastructure.config.json_runtime_config_initializer import (
    JsonRuntimeConfigInitializer,
)

pytestmark = pytest.mark.unit

_SETTINGS_ENV_NAMES = (
    "AGENT_RUNTIME_CONFIG_FILE",
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

    assert settings.db_path == str(tmp_path / "home/.skiller/runtime/global.db")


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
    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_FILE", str(config_path))

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
    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_FILE", str(config_path))
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
    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_FILE", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="AGENT_RUNTIME_CONFIG_FILE does not exist"):
        settings_module.get_settings()


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in _SETTINGS_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)


def test_default_database_is_shared_between_working_directories(monkeypatch, tmp_path):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    _initialize_config()
    settings = settings_module.get_settings()
    monkeypatch.chdir(second)
    assert settings_module.get_settings().db_path == settings.db_path
    config_path = tmp_path / "home/.skiller/settings/config.json"
    assert json.loads(config_path.read_text()) == {
        "runtime": {"db_path": "~/.skiller/runtime/global.db"}
    }


def test_default_database_preserves_other_global_options(monkeypatch, tmp_path):
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_path = tmp_path / "home/.skiller/settings/config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({"runtime": {"log_level": "DEBUG"}, "flow_paths": ["/flows"]})
    )
    _initialize_config()
    config = json.loads(config_path.read_text())
    assert config["runtime"] == {"log_level": "DEBUG", "db_path": "~/.skiller/runtime/global.db"}
    assert config["flow_paths"] == ["/flows"]


@pytest.mark.parametrize("development_file", [False, True])
def test_explicit_database_does_not_create_global_config(monkeypatch, tmp_path, development_file):
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    if development_file:
        (tmp_path / ".env.development").write_text("AGENT_DB_PATH=local.db\n")
    else:
        monkeypatch.setenv("AGENT_DB_PATH", "local.db")
    _initialize_config()
    assert settings_module.get_settings().db_path == "local.db"
    assert not (tmp_path / "home/.skiller/settings/config.json").exists()


def _initialize_config():
    template = Path(__file__).resolve().parents[6] / "apps/agents/flows/agent.flows.json"
    JsonRuntimeConfigInitializer(flows_profile_template=template).initialize(
        initialize_database_config=True,
    )


def test_settings_does_not_write_files(monkeypatch, tmp_path):
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    settings_module.get_settings()
    assert not (tmp_path / "home").exists()


def test_initializer_preserves_existing_profiles_and_database(monkeypatch, tmp_path):
    _clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _initialize_config()
    profile = tmp_path / "home/.skiller/settings/agent.flows.json"
    assert json.loads(profile.read_text())["tools"]["shell"]["allowlist_enabled"] is True
    profile.write_text('{"loop":{"max_turns":7}}')
    config = profile.with_name("config.json")
    config.write_text('{"runtime":{"db_path":"custom.db"}}')
    _initialize_config()
    assert profile.read_text() == '{"loop":{"max_turns":7}}'
    assert config.read_text() == '{"runtime":{"db_path":"custom.db"}}'
    assert settings_module.get_settings().db_path == "custom.db"
