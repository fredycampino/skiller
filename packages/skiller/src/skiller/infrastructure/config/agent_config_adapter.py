from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLLMClientType,
    AgentLLMConfig,
    AgentLLMProviderConfig,
    AgentLLMProviderType,
    AgentLoopConfig,
)

DEFAULT_AGENT_LOOP_MAX_TURNS = 10
DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS = 5
DEFAULT_AGENT_CONTEXT_COMPACTION_ENABLED = False
DEFAULT_AGENT_CONTEXT_COMPACTION_MAX_TOTAL_TOKENS_RATIO = 0.8
DEFAULT_AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED = True
DEFAULT_AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS = 600
DEFAULT_AGENT_EVENT_OUTPUT_MAX_JSON_CHARS = 4000
DEFAULT_AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS = 20


class _AgentConfigModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    llm: "_LLMConfigModel"
    agent: "_AgentRuntimeConfigModel" = Field(default_factory=lambda: _AgentRuntimeConfigModel())


class _LLMConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: str
    providers: dict[str, "_LLMProviderConfigModel"]


class _LLMProviderConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AgentLLMProviderType
    client_type: AgentLLMClientType
    model: str
    base_url: str
    timeout_seconds: float = Field(gt=0)
    context_window_tokens: int = Field(gt=0)
    api_key: str | None = None
    api_key_env: str | None = None
    api_key_file: str | None = None


class _AgentRuntimeConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loop: "_LoopConfigModel" = Field(default_factory=lambda: _LoopConfigModel())
    context: "_ContextConfigModel" = Field(default_factory=lambda: _ContextConfigModel())
    event_output: "_EventOutputConfigModel" = Field(
        default_factory=lambda: _EventOutputConfigModel(),
    )


class _LoopConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: int = Field(default=DEFAULT_AGENT_LOOP_MAX_TURNS, gt=0)
    max_tool_calls: int = Field(default=DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS, gt=0)


class _ContextConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compaction: "_CompactionConfigModel" = Field(
        default_factory=lambda: _CompactionConfigModel(),
    )


class _CompactionConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = DEFAULT_AGENT_CONTEXT_COMPACTION_ENABLED
    max_total_tokens_ratio: float = Field(
        default=DEFAULT_AGENT_CONTEXT_COMPACTION_MAX_TOTAL_TOKENS_RATIO,
        gt=0,
        le=1,
    )


class _EventOutputConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truncate: "_EventOutputTruncateConfigModel" = Field(
        default_factory=lambda: _EventOutputTruncateConfigModel(),
    )


class _EventOutputTruncateConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = DEFAULT_AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED
    max_text_chars: int = Field(default=DEFAULT_AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS, gt=0)
    max_json_chars: int = Field(default=DEFAULT_AGENT_EVENT_OUTPUT_MAX_JSON_CHARS, gt=0)
    max_array_items: int = Field(default=DEFAULT_AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS, gt=0)


def agent_config_from_json(
    raw_config: dict[str, object],
    *,
    env: Mapping[str, str],
) -> AgentConfig:
    try:
        config = _AgentConfigModel.model_validate(raw_config)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid agent config: {exc}") from exc

    default_provider = env.get("AGENT_LLM_PROVIDER", config.llm.default_provider)
    return AgentConfig(
        llm=AgentLLMConfig(
            default_provider=default_provider,
            providers={
                provider_id: _build_provider_config(
                    provider=provider,
                    selected=provider_id == default_provider,
                    env=env,
                )
                for provider_id, provider in config.llm.providers.items()
            },
        ),
        loop=_build_loop_config(config.agent.loop, env=env),
        context=AgentContextConfig(
            compaction=AgentContextCompactionConfig(
                enabled=config.agent.context.compaction.enabled,
                max_total_tokens_ratio=config.agent.context.compaction.max_total_tokens_ratio,
            ),
        ),
        event_output=_build_event_output_config(config.agent.event_output, env=env),
    )


def _build_provider_config(
    *,
    provider: _LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> AgentLLMProviderConfig:
    return AgentLLMProviderConfig(
        provider=provider.provider,
        client_type=provider.client_type,
        model=_provider_env(provider.provider, selected, "MODEL", env) or provider.model,
        api_key=_resolve_api_key(provider=provider, selected=selected, env=env),
        base_url=_provider_env(provider.provider, selected, "BASE_URL", env) or provider.base_url,
        timeout_seconds=_provider_timeout_seconds(provider=provider, selected=selected, env=env),
        context_window_tokens=provider.context_window_tokens,
    )


def _build_loop_config(
    loop: _LoopConfigModel,
    *,
    env: Mapping[str, str],
) -> AgentLoopConfig:
    return AgentLoopConfig(
        max_turns=_env_positive_int("AGENT_LOOP_MAX_TURNS", loop.max_turns, env),
        max_tool_calls=_env_positive_int(
            "AGENT_LOOP_MAX_TOOL_CALLS",
            loop.max_tool_calls,
            env,
        ),
    )


def _build_event_output_config(
    event_output: _EventOutputConfigModel,
    *,
    env: Mapping[str, str],
) -> AgentEventOutputConfig:
    truncate = event_output.truncate
    return AgentEventOutputConfig(
        truncate=AgentEventOutputTruncateConfig(
            enabled=_env_bool("AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED", truncate.enabled, env),
            max_text_chars=_env_positive_int(
                "AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS",
                truncate.max_text_chars,
                env,
            ),
            max_json_chars=_env_positive_int(
                "AGENT_EVENT_OUTPUT_MAX_JSON_CHARS",
                truncate.max_json_chars,
                env,
            ),
            max_array_items=_env_positive_int(
                "AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS",
                truncate.max_array_items,
                env,
            ),
        ),
    )


def _resolve_api_key(
    *,
    provider: _LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> str:
    value = _provider_env(provider.provider, selected, "API_KEY", env)
    if value is not None:
        return value

    if provider.api_key is not None:
        return provider.api_key

    if provider.api_key_env is not None:
        value = env.get(provider.api_key_env)
        if value is None:
            raise RuntimeError(
                f"Missing environment variable for api_key_env: {provider.api_key_env}"
            )
        return value

    if provider.api_key_file is None:
        raise RuntimeError("LLM provider requires api_key")

    secret_path = Path(provider.api_key_file).expanduser()
    if not secret_path.exists():
        raise RuntimeError(f"Missing api_key_file: {_display_path(secret_path)}")
    return secret_path.read_text(encoding="utf-8").strip()


def _provider_timeout_seconds(
    *,
    provider: _LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> float:
    value = _provider_env(provider.provider, selected, "TIMEOUT_SECONDS", env)
    if value is None:
        return provider.timeout_seconds
    return _positive_float_from_env(
        value,
        f"AGENT_{provider.provider.value.upper()}_TIMEOUT_SECONDS",
    )


def _provider_env(
    provider_type: AgentLLMProviderType,
    selected: bool,
    name: str,
    env: Mapping[str, str],
) -> str | None:
    if not selected:
        return None
    env_name = f"AGENT_{provider_type.value.upper()}_{name}"
    return env.get(env_name)


def _env_bool(env_name: str, default: bool, env: Mapping[str, str]) -> bool:
    value = env.get(env_name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{env_name} must be a boolean")


def _env_positive_int(env_name: str, default: int, env: Mapping[str, str]) -> int:
    value = env.get(env_name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{env_name} must be a positive integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{env_name} must be a positive integer")
    return parsed


def _positive_float_from_env(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"{label} must be a positive number") from exc
    if parsed <= 0:
        raise RuntimeError(f"{label} must be a positive number")
    return parsed


def _display_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(expanded)
