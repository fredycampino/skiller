import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: str = "./runtime.db"
    llm_provider: str = "null"
    fake_llm_response_json: str = (
        '{"summary":"fake summary","severity":"low","next_action":"retry"}'
    )
    fake_llm_model: str = "fake-llm"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_model: str = "MiniMax-M2.5"
    minimax_timeout_seconds: float = 30.0
    log_level: str = "INFO"
    webhooks_host: str = "127.0.0.1"
    webhooks_port: int = 8001
    whatsapp_bridge_host: str = "127.0.0.1"
    whatsapp_bridge_port: int = 8002
    whatsapp_bridge_send_timeout_seconds: float = 10.0


def get_settings() -> Settings:
    config = _load_config()
    provider_name = _string_setting(
        "AGENT_LLM_PROVIDER",
        config,
        ("llm", "default_provider"),
        "null",
    )
    provider_config = _provider_config(config, provider_name)
    provider_type = str(provider_config.get("type", provider_name)).strip().lower()

    return Settings(
        db_path=_path_setting("AGENT_DB_PATH", config, ("runtime", "db_path"), "./runtime.db"),
        llm_provider=provider_type,
        fake_llm_response_json=_json_string_setting(
            "AGENT_FAKE_LLM_RESPONSE_JSON",
            provider_config,
            "response_json",
            '{"summary":"fake summary","severity":"low","next_action":"retry"}',
        ),
        fake_llm_model=_provider_string_setting(
            "AGENT_FAKE_LLM_MODEL",
            provider_config,
            "model",
            "fake-llm",
        ),
        minimax_api_key=_secret_setting(
            "AGENT_MINIMAX_API_KEY",
            provider_config,
            "api_key",
            "api_key_env",
            "api_key_file",
        ),
        minimax_base_url=_provider_string_setting(
            "AGENT_MINIMAX_BASE_URL",
            provider_config,
            "base_url",
            "https://api.minimax.io/v1",
        ),
        minimax_model=_provider_string_setting(
            "AGENT_MINIMAX_MODEL",
            provider_config,
            "model",
            "MiniMax-M2.5",
        ),
        minimax_timeout_seconds=float(
            _provider_setting(
                "AGENT_MINIMAX_TIMEOUT_SECONDS",
                provider_config,
                "timeout_seconds",
                30,
            )
        ),
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
    )


def _load_config() -> dict[str, object]:
    explicit_path = os.environ.get("AGENT_CONFIG_FILE", "").strip()
    config_path = (
        Path(explicit_path).expanduser()
        if explicit_path
        else Path.home() / ".skiller" / "settings" / "config.json"
    )
    if not config_path.exists():
        if explicit_path:
            raise RuntimeError(f"AGENT_CONFIG_FILE does not exist: {config_path}")
        return {}

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON config file: {config_path}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Config file must contain a JSON object: {config_path}")
    return payload


def _provider_config(config: dict[str, object], provider_name: str) -> dict[str, object]:
    providers = _object_at(config, ("llm", "providers"))
    if provider_name in providers:
        provider = providers[provider_name]
        if isinstance(provider, dict):
            return dict(provider)
        raise RuntimeError(f"LLM provider config must be an object: {provider_name}")
    return {"type": provider_name}


def _object_at(config: dict[str, object], path: tuple[str, ...]) -> dict[str, object]:
    value: object = config
    for key in path:
        if not isinstance(value, dict):
            return {}
        value = value.get(key, {})
    return value if isinstance(value, dict) else {}


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


def _provider_setting(
    env_name: str,
    provider_config: dict[str, object],
    config_name: str,
    default: object,
) -> object:
    if env_name in os.environ:
        return os.environ[env_name]
    value = provider_config.get(config_name)
    if value is not None:
        return value
    return default


def _provider_string_setting(
    env_name: str,
    provider_config: dict[str, object],
    config_name: str,
    default: str,
) -> str:
    return str(_provider_setting(env_name, provider_config, config_name, default)).strip()


def _json_string_setting(
    env_name: str,
    provider_config: dict[str, object],
    config_name: str,
    default: str,
) -> str:
    value = _provider_setting(env_name, provider_config, config_name, default)
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _secret_setting(
    env_name: str,
    provider_config: dict[str, object],
    inline_name: str,
    env_ref_name: str,
    file_name: str,
) -> str:
    if env_name in os.environ:
        return os.environ[env_name]

    inline_value = provider_config.get(inline_name)
    if isinstance(inline_value, str) and inline_value.strip():
        return inline_value.strip()

    env_ref = provider_config.get(env_ref_name)
    if isinstance(env_ref, str) and env_ref.strip():
        return os.environ.get(env_ref.strip(), "").strip()

    file_ref = provider_config.get(file_name)
    if isinstance(file_ref, str) and file_ref.strip():
        secret_path = Path(file_ref).expanduser()
        if not secret_path.exists():
            raise RuntimeError(f"Configured secret file does not exist: {secret_path}")
        return secret_path.read_text(encoding="utf-8").strip()

    return ""


def _value_at(config: dict[str, object], path: tuple[str, ...]) -> object | None:
    value: object = config
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
