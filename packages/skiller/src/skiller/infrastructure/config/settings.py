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
            "SKILLER_DB_PATH",
            env_file,
            config,
            ("runtime", "db_path"),
            "~/.skiller/runtime/global.db",
        ),
        log_level=str(_config_setting(config, ("runtime", "log_level"), "INFO")).strip(),
        webhooks_host=str(_config_setting(config, ("webhooks", "host"), "127.0.0.1")).strip(),
        webhooks_port=int(_config_setting(config, ("webhooks", "port"), 8001)),
    )


def get_config_file_environment_value() -> str | None:
    env_file = load_development_env()
    config_path, explicit = resolve_json_config_path(
        env_name="SKILLER_RUNTIME_CONFIG_FILE",
        env_file=env_file,
        default_path=Path.home() / ".skiller" / "settings" / "config.json",
    )
    if not explicit:
        return None
    return str(config_path)


def _config_setting(
    config: dict[str, object], path: tuple[str, ...], default: object,
) -> object:
    value = _value_at(config, path)
    return default if value is None else value


def _path_setting(
    env_name: str,
    env_file: dict[str, str],
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    value = str(
        os.environ.get(env_name, env_file.get(env_name, _config_setting(config, path, default)))
    ).strip()
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
