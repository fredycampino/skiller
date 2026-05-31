import json
import os
from pathlib import Path

from skiller.infrastructure.config.settings_model import Settings


def get_settings() -> Settings:
    env_file = _load_development_env()
    config = _load_config(env_file)

    return Settings(
        db_path=_path_setting(
            "AGENT_DB_PATH",
            env_file,
            config,
            ("runtime", "db_path"),
            "./runtime.db",
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
        whatsapp_bridge_host=_string_setting(
            "AGENT_WHATSAPP_BRIDGE_HOST",
            env_file,
            config,
            ("whatsapp", "bridge", "host"),
            "127.0.0.1",
        ),
        whatsapp_bridge_port=int(
            _setting(
                "AGENT_WHATSAPP_BRIDGE_PORT",
                env_file,
                config,
                ("whatsapp", "bridge", "port"),
                8002,
            )
        ),
        whatsapp_bridge_send_timeout_seconds=float(
            _setting(
                "AGENT_WHATSAPP_BRIDGE_SEND_TIMEOUT_SECONDS",
                env_file,
                config,
                ("whatsapp", "bridge", "send_timeout_seconds"),
                10,
            )
        ),
    )


def _load_development_env() -> dict[str, str]:
    env_path = Path.cwd() / ".env.development"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    lines = env_path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise RuntimeError(f"Invalid .env.development line {line_number}: missing '='")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise RuntimeError(f"Invalid .env.development line {line_number}: empty key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _load_config(env_file: dict[str, str]) -> dict[str, object]:
    config_path, explicit = _resolve_json_config_path(
        env_name="AGENT_CONFIG_FILE",
        env_file=env_file,
        default_path=Path.home() / ".skiller" / "settings" / "config.json",
    )
    return _load_json_config_file(
        config_path=config_path,
        env_name="AGENT_CONFIG_FILE",
        explicit=explicit,
    )


def _resolve_json_config_path(
    *,
    env_name: str,
    env_file: dict[str, str],
    default_path: Path,
) -> tuple[Path, bool]:
    explicit_path = os.environ.get(env_name, "").strip()
    if not explicit_path:
        explicit_path = env_file.get(env_name, "").strip()
    config_path = Path(explicit_path).expanduser() if explicit_path else default_path
    return config_path, bool(explicit_path)


def _load_json_config_file(
    *,
    config_path: Path,
    env_name: str,
    explicit: bool,
) -> dict[str, object]:
    if not config_path.exists():
        if explicit:
            raise RuntimeError(f"{env_name} does not exist: {config_path}")
        return {}

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        display_path = _display_path(config_path)
        raise RuntimeError(
            f"Invalid JSON config file: {display_path} "
            f"(line {exc.lineno}, column {exc.colno})"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Config file must contain a JSON object: {config_path}")
    return payload


def _display_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(expanded)


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
