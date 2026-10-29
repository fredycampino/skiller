import os
from pathlib import Path

from skiller.infrastructure.config.settings_model import Settings
from skiller.infrastructure.config.settings_source import (
    load_config,
    load_development_env,
    resolve_json_config_path,
)


def get_settings() -> Settings:
    env_file = load_development_env()
    config = load_config(env_file)

    return Settings(
        db_path=_path_setting(
            "AGENT_DB_PATH",
            env_file,
            config,
            ("runtime", "db_path"),
            "~/.skiller/runtime/global.db",
        ),
        log_level=_string_setting(
            "AGENT_LOG_LEVEL",
            env_file,
            config,
            ("runtime", "log_level"),
            "INFO",
        ),
        webhooks_host=_string_setting(
            "AGENT_WEBHOOKS_HOST",
            env_file,
            config,
            ("webhooks", "host"),
            "127.0.0.1",
        ),
        webhooks_port=int(
            _setting("AGENT_WEBHOOKS_PORT", env_file, config, ("webhooks", "port"), 8001)
        ),
    )


def get_config_file_environment_value() -> str | None:
    env_file = load_development_env()
    config_path, explicit = resolve_json_config_path(
        env_name="AGENT_RUNTIME_CONFIG_FILE",
        env_file=env_file,
        default_path=Path.home() / ".skiller" / "settings" / "config.json",
    )
    if not explicit:
        return None
    return str(config_path)


def _setting(
    env_name: str,
    env_file: dict[str, str],
    config: dict[str, object],
    path: tuple[str, ...],
    default: object,
) -> object:
    if env_name in os.environ:
        return os.environ[env_name]
    if env_name in env_file:
        return env_file[env_name]
    value = _value_at(config, path)
    if value is not None:
        return value
    return default


def _string_setting(
    env_name: str,
    env_file: dict[str, str],
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    return str(_setting(env_name, env_file, config, path, default)).strip()


def _path_setting(
    env_name: str,
    env_file: dict[str, str],
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    value = _string_setting(env_name, env_file, config, path, default)
    if value.startswith("~"):
        return str(Path(value).expanduser())
    return value


def _value_at(config: dict[str, object], path: tuple[str, ...]) -> object | None:
    value: object = config
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


__all__ = ["Settings", "get_settings"]
