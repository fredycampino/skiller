import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LlmSettings:
    llm_provider: str
    fake_llm_response_json: str
    fake_llm_model: str
    minimax_api_key: str
    minimax_base_url: str
    minimax_model: str
    minimax_timeout_seconds: float


def resolve_llm_settings(agent_config_file: str | Path) -> LlmSettings:
    agent_config = _load_agent_config_file(agent_config_file)
    fallback_llm_config = _load_fallback_llm_config()
    llm_config = _deep_merge_dicts(
        fallback_llm_config,
        _extract_llm_config(agent_config),
    )
    fallback_default_provider = _require_string_setting(
        fallback_llm_config,
        "default_provider",
    )
    fallback_fake_provider = _require_provider_config(fallback_llm_config, "fake")
    fallback_minimax_provider = _require_provider_config(fallback_llm_config, "minimax")
    fallback_fake_response_json = _require_setting(fallback_fake_provider, "response_json")
    fallback_fake_model = _require_string_setting(fallback_fake_provider, "model")
    fallback_minimax_base_url = _require_string_setting(fallback_minimax_provider, "base_url")
    fallback_minimax_model = _require_string_setting(fallback_minimax_provider, "model")
    fallback_minimax_timeout_seconds = _require_setting(
        fallback_minimax_provider,
        "timeout_seconds",
    )
    provider_name = _llm_string_setting(
        "AGENT_LLM_PROVIDER",
        llm_config,
        ("default_provider",),
        fallback_default_provider,
    )
    provider_config = _provider_config(llm_config, provider_name)
    provider_type = str(
        provider_config.get("client_type", provider_config.get("type", provider_name))
    ).strip().lower()

    return LlmSettings(
        llm_provider=provider_type,
        fake_llm_response_json=_json_string_setting(
            "AGENT_FAKE_LLM_RESPONSE_JSON",
            provider_config,
            "response_json",
            _json_default(fallback_fake_response_json),
        ),
        fake_llm_model=_provider_string_setting(
            "AGENT_FAKE_LLM_MODEL",
            provider_config,
            "model",
            fallback_fake_model,
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
            fallback_minimax_base_url,
        ),
        minimax_model=_provider_string_setting(
            "AGENT_MINIMAX_MODEL",
            provider_config,
            "model",
            fallback_minimax_model,
        ),
        minimax_timeout_seconds=float(
            _provider_setting(
                "AGENT_MINIMAX_TIMEOUT_SECONDS",
                provider_config,
                "timeout_seconds",
                fallback_minimax_timeout_seconds,
            )
        ),
    )


def _extract_llm_config(agent_config: dict[str, object]) -> dict[str, object]:
    raw = agent_config.get("llm")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RuntimeError("agent.json field 'llm' must be a JSON object")
    return dict(raw)


def _load_fallback_llm_config() -> dict[str, object]:
    fallback_path = Path(__file__).with_name("config.json")
    if not fallback_path.exists():
        raise RuntimeError(f"Missing fallback LLM config file: {fallback_path}")
    try:
        payload = json.loads(fallback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid fallback LLM config file: {fallback_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Fallback LLM config must be a JSON object: {fallback_path}")
    return payload


def _load_agent_config_file(agent_config_file: str | Path) -> dict[str, object]:
    config_path = Path(agent_config_file).expanduser()
    if not config_path.exists():
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


def _llm_string_setting(
    env_name: str,
    llm_config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    if env_name in os.environ:
        return str(os.environ[env_name]).strip()
    value = _value_at(llm_config, path)
    if value is None:
        return default
    return str(value).strip()


def _provider_config(llm_config: dict[str, object], provider_name: str) -> dict[str, object]:
    providers = llm_config.get("providers", {})
    if isinstance(providers, dict) and provider_name in providers:
        provider = providers[provider_name]
        if isinstance(provider, dict):
            return dict(provider)
        raise RuntimeError(f"LLM provider config must be an object: {provider_name}")
    return {"type": provider_name}


def _require_provider_config(
    llm_config: dict[str, object],
    provider_name: str,
) -> dict[str, object]:
    providers = llm_config.get("providers")
    if not isinstance(providers, dict):
        raise RuntimeError("fallback LLM config must define 'providers' as JSON object")

    provider = providers.get(provider_name)
    if not isinstance(provider, dict):
        raise RuntimeError(
            f"fallback LLM config must define providers.{provider_name} as JSON object"
        )
    return provider


def _require_setting(config: dict[str, object], key: str) -> object:
    if key not in config:
        raise RuntimeError(f"fallback LLM config is missing required key: {key}")
    value = config[key]
    if value is None:
        raise RuntimeError(f"fallback LLM config key '{key}' must not be null")
    return value


def _require_string_setting(config: dict[str, object], key: str) -> str:
    value = _require_setting(config, key)
    if not isinstance(value, str):
        raise RuntimeError(f"fallback LLM config key '{key}' must be a string")
    stripped = value.strip()
    if not stripped:
        raise RuntimeError(f"fallback LLM config key '{key}' must not be empty")
    return stripped


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


def _json_default(value: object) -> str:
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
