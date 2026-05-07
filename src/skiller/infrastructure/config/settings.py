import json
import os
from pathlib import Path

from skiller.infrastructure.agent.config import resolve_agent_settings
from skiller.infrastructure.config.settings_model import Settings
from skiller.infrastructure.llm.config import resolve_llm_settings
from skiller.infrastructure.tools.shell.config import resolve_shell_settings


def get_settings() -> Settings:
    config = _load_config()
    agent_config_path, agent_explicit = _resolve_json_config_path(
        env_name="AGENT_AGENT_CONFIG_FILE",
        default_path=Path.home() / ".skiller" / "settings" / "agent.json",
    )
    agent_config = _load_json_config_file(
        config_path=agent_config_path,
        env_name="AGENT_AGENT_CONFIG_FILE",
        explicit=agent_explicit,
    )
    agent_runtime_config = _extract_agent_runtime_config(agent_config)
    if agent_runtime_config:
        _merge_agent_config(config, agent_runtime_config)

    agent_settings = resolve_agent_settings(agent_config_path)
    llm_settings = resolve_llm_settings(agent_config_path)
    shell_settings = resolve_shell_settings(agent_config_path)

    return Settings(
        db_path=_path_setting("AGENT_DB_PATH", config, ("runtime", "db_path"), "./runtime.db"),
        llm_provider=llm_settings.llm_provider,
        fake_llm_response_json=llm_settings.fake_llm_response_json,
        fake_llm_model=llm_settings.fake_llm_model,
        minimax_api_key=llm_settings.minimax_api_key,
        minimax_base_url=llm_settings.minimax_base_url,
        minimax_model=llm_settings.minimax_model,
        minimax_timeout_seconds=llm_settings.minimax_timeout_seconds,
        log_level=_string_setting("AGENT_LOG_LEVEL", config, ("runtime", "log_level"), "INFO"),
        webhooks_host=_string_setting(
            "AGENT_WEBHOOKS_HOST",
            config,
            ("webhooks", "host"),
            "127.0.0.1",
        ),
        webhooks_port=int(_setting("AGENT_WEBHOOKS_PORT", config, ("webhooks", "port"), 8001)),
        whatsapp_bridge_host=_string_setting(
            "AGENT_WHATSAPP_BRIDGE_HOST",
            config,
            ("whatsapp", "bridge", "host"),
            "127.0.0.1",
        ),
        whatsapp_bridge_port=int(
            _setting("AGENT_WHATSAPP_BRIDGE_PORT", config, ("whatsapp", "bridge", "port"), 8002)
        ),
        whatsapp_bridge_send_timeout_seconds=float(
            _setting(
                "AGENT_WHATSAPP_BRIDGE_SEND_TIMEOUT_SECONDS",
                config,
                ("whatsapp", "bridge", "send_timeout_seconds"),
                10,
            )
        ),
        agent_shell_allowlist_enabled=shell_settings.allowlist_enabled,
        agent_shell_allowlist_workspace=shell_settings.workspace,
        agent_shell_allowlist_allow_env_prefix=shell_settings.allow_env_prefix,
        agent_shell_allowlist_allowed_commands=shell_settings.allowed_commands,
        agent_shell_sandbox_enabled=shell_settings.sandbox_enabled,
        agent_event_output_truncate_enabled=_bool_setting(
            "AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED",
            config,
            ("agent", "event_output", "truncate", "enabled"),
            True,
        ),
        agent_event_output_pii_enabled=_bool_setting(
            "AGENT_EVENT_OUTPUT_PII_ENABLED",
            config,
            ("agent", "event_output", "pii", "enabled"),
            True,
        ),
        agent_event_output_secrets_enabled=_bool_setting(
            "AGENT_EVENT_OUTPUT_SECRETS_ENABLED",
            config,
            ("agent", "event_output", "secrets", "enabled"),
            True,
        ),
        agent_event_output_max_text_chars=_positive_int_setting_with_fallback(
            "AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS",
            config,
            primary_path=("agent", "event_output", "truncate", "max_text_chars"),
            fallback_path=("agent", "event_output", "max_text_chars"),
            default=600,
        ),
        agent_event_output_max_json_chars=_positive_int_setting_with_fallback(
            "AGENT_EVENT_OUTPUT_MAX_JSON_CHARS",
            config,
            primary_path=("agent", "event_output", "truncate", "max_json_chars"),
            fallback_path=("agent", "event_output", "max_json_chars"),
            default=4000,
        ),
        agent_event_output_max_array_items=_positive_int_setting_with_fallback(
            "AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS",
            config,
            primary_path=("agent", "event_output", "truncate", "max_array_items"),
            fallback_path=("agent", "event_output", "max_array_items"),
            default=20,
        ),
        agent_loop_max_turns=agent_settings.loop_max_turns,
        agent_loop_max_tool_calls=agent_settings.loop_max_tool_calls,
    )


def _load_config() -> dict[str, object]:
    config_path, explicit = _resolve_json_config_path(
        env_name="AGENT_CONFIG_FILE",
        default_path=Path.home() / ".skiller" / "settings" / "config.json",
    )
    return _load_json_config_file(
        config_path=config_path,
        env_name="AGENT_CONFIG_FILE",
        explicit=explicit,
    )


def _resolve_json_config_path(*, env_name: str, default_path: Path) -> tuple[Path, bool]:
    explicit_path = os.environ.get(env_name, "").strip()
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


def _merge_agent_config(config: dict[str, object], agent_config: dict[str, object]) -> None:
    raw_current = config.get("agent")
    current_agent = raw_current if isinstance(raw_current, dict) else {}
    merged = _deep_merge_dicts(current_agent, agent_config)
    config["agent"] = merged


def _extract_agent_runtime_config(agent_config: dict[str, object]) -> dict[str, object]:
    if not agent_config:
        return {}

    root_runtime = {
        key: value
        for key, value in agent_config.items()
        if key not in {"agent", "llm", "shell"}
    }

    explicit = agent_config.get("agent")
    if explicit is None:
        return root_runtime
    if not isinstance(explicit, dict):
        raise RuntimeError("agent.json field 'agent' must be a JSON object")

    return _deep_merge_dicts(root_runtime, explicit)


def _deep_merge_dicts(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = dict(left)
    for key, right_value in right.items():
        left_value = merged.get(key)
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            merged[key] = _deep_merge_dicts(left_value, right_value)
            continue
        merged[key] = right_value
    return merged


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
    config: dict[str, object],
    path: tuple[str, ...],
    default: object,
) -> object:
    if env_name in os.environ:
        return os.environ[env_name]
    value = _value_at(config, path)
    if value is not None:
        return value
    return default


def _string_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    return str(_setting(env_name, config, path, default)).strip()


def _path_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    value = _string_setting(env_name, config, path, default)
    if value.startswith("~"):
        return str(Path(value).expanduser())
    return value


def _positive_int_setting_with_fallback(
    env_name: str,
    config: dict[str, object],
    *,
    primary_path: tuple[str, ...],
    fallback_path: tuple[str, ...],
    default: int,
) -> int:
    if env_name in os.environ:
        value = os.environ[env_name]
    else:
        primary_value = _value_at(config, primary_path)
        if primary_value is not None:
            value = primary_value
        else:
            fallback_value = _value_at(config, fallback_path)
            value = fallback_value if fallback_value is not None else default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{env_name} must be a positive integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{env_name} must be a positive integer")
    return parsed


def _bool_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: bool,
) -> bool:
    value = _setting(env_name, config, path, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise RuntimeError(f"{env_name} must be a boolean")


def _value_at(config: dict[str, object], path: tuple[str, ...]) -> object | None:
    value: object = config
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


__all__ = ["Settings", "get_settings"]
