from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMModel,
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
)
from skiller.domain.tool.tool_contract import (
    ConfiguredTool,
    ToolDefinition,
    ToolRuntimeConfig,
    ToolRuntimeConfigs,
)
from skiller.infrastructure.config.agent_config_schema import (
    AgentConfigModel,
    EventOutputConfigModel,
    LLMProviderConfigModel,
    LoopConfigModel,
)


class AgentConfigMapper:
    def __init__(
        self,
        *,
        env: Mapping[str, str],
        tools: tuple[ToolDefinition, ...] = (),
    ) -> None:
        self.env = env
        self.tools = tools

    def from_json(self, raw_config: dict[str, object]) -> AgentConfig:
        if "agent" in raw_config:
            raise ValueError("agent.json field 'agent' is not supported")

        try:
            config = AgentConfigModel.model_validate(raw_config)
        except ValidationError as exc:
            raise ValueError(f"Invalid agent config: {exc}") from exc

        default_provider = _provider_type(
            self.env.get("AGENT_LLM_PROVIDER", config.llm.default_provider)
        )
        providers: list[AgentLLMProvider] = []
        for provider_id, provider in config.providers.items():
            provider_type = _provider_type(provider_id)
            selected = provider_type == default_provider
            llm_provider = _build_provider(
                provider_type=provider_type,
                provider=provider,
                selected=selected,
                env=self.env,
            )
            providers.append(llm_provider)

        compaction = AgentContextCompactionConfig(
            enabled=config.context.compaction.enabled,
            max_total_tokens_ratio=config.context.compaction.max_total_tokens_ratio,
        )
        context = AgentContextConfig(
            compaction=compaction,
        )
        llm = AgentLLMProviderList(
            default_provider=default_provider,
            providers=tuple(providers),
        )
        loop = _build_loop_config(config.loop, env=self.env)
        event_output = _build_event_output_config(config.event_output, env=self.env)
        tools = _build_tool_runtime_configs(
            raw_tools=config.tools,
            tools=self.tools,
        )

        return AgentConfig(
            llm=llm,
            loop=loop,
            context=context,
            event_output=event_output,
            tools=tools,
        )


def _build_provider(
    *,
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> AgentLLMProvider:
    raw_model = _provider_env(provider_type, selected, "MODEL", env) or provider.model
    model = _provider_model(provider_type=provider_type, value=raw_model)
    api_key = _api_key_for_provider(
        provider_type=provider_type,
        provider=provider,
        selected=selected,
        env=env,
    )
    credentials_file = provider.credentials_file
    _validate_provider_credentials(
        provider_type=provider_type,
        api_key=api_key,
        credentials_file=credentials_file,
    )

    return AgentLLMProvider(
        type=provider_type,
        model=model,
        api_key=api_key,
        timeout_seconds=_provider_timeout_seconds(
            provider_type=provider_type,
            provider=provider,
            selected=selected,
            env=env,
        ),
        context_window_tokens=provider.context_window_tokens,
        credentials_file=credentials_file,
    )


def _build_tool_runtime_configs(
    *,
    raw_tools: dict[str, dict[str, object]],
    tools: tuple[ToolDefinition, ...],
) -> ToolRuntimeConfigs:
    known_tool_names = {tool.name for tool in tools}
    unknown_tool_names = sorted(set(raw_tools) - known_tool_names)
    if unknown_tool_names:
        unknown_values = ", ".join(unknown_tool_names)
        raise ValueError(f"Unknown agent tool config: {unknown_values}")

    runtime_config_items: list[ToolRuntimeConfig] = []
    for tool in tools:
        if not isinstance(tool, ConfiguredTool):
            continue
        raw_tool = raw_tools.get(tool.name, {})
        runtime_config_items.append(tool.to_runtime_config(raw_tool))
    return ToolRuntimeConfigs(items=tuple(runtime_config_items))


def _provider_model(
    *,
    provider_type: AgentLLMProviderType,
    value: str,
) -> AgentLLMModel:
    try:
        model = AgentLLMModel(value)
    except ValueError as exc:
        raise _unsupported_provider_model_error(
            provider_type=provider_type,
            model=value,
        ) from exc

    supported_models = _supported_provider_models(provider_type)
    if model in supported_models:
        return model

    raise _unsupported_provider_model_error(
        provider_type=provider_type,
        model=value,
    )


def _unsupported_provider_model_error(
    *,
    provider_type: AgentLLMProviderType,
    model: str,
) -> ValueError:
    supported_models = _supported_provider_models(provider_type)
    supported_values = ", ".join(model.value for model in supported_models)
    return ValueError(
        f"Unsupported model='{model}' for provider='{provider_type.value}'. "
        f"Supported models: {supported_values or 'none'}."
    )


def _supported_provider_models(
    provider_type: AgentLLMProviderType,
) -> tuple[AgentLLMModel, ...]:
    if provider_type == AgentLLMProviderType.NULL:
        return (AgentLLMModel.NULL1,)
    if provider_type == AgentLLMProviderType.FAKE:
        return (AgentLLMModel.MODEL1,)
    if provider_type == AgentLLMProviderType.MINIMAX:
        return (AgentLLMModel.MINIMAX_M2_5, AgentLLMModel.MINIMAX_M2_7)
    if provider_type == AgentLLMProviderType.CODEX:
        return (
            AgentLLMModel.GPT_5_3_CODEX,
            AgentLLMModel.GPT_5_4,
            AgentLLMModel.GPT_5_5,
        )
    raise ValueError(f"Unsupported LLM provider: {provider_type.value}")


def _api_key_for_provider(
    *,
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> str | None:
    if provider_type == AgentLLMProviderType.CODEX:
        return None
    if provider_type == AgentLLMProviderType.FAKE:
        return None
    if provider_type == AgentLLMProviderType.NULL:
        return None
    return _resolve_api_key(
        provider_type=provider_type,
        provider=provider,
        selected=selected,
        env=env,
    )


def _validate_provider_credentials(
    *,
    provider_type: AgentLLMProviderType,
    api_key: str | None,
    credentials_file: str | None,
) -> None:
    if provider_type == AgentLLMProviderType.CODEX:
        if credentials_file is None or not credentials_file.strip():
            raise ValueError("LLM provider requires credentials_file")
        return

    if provider_type == AgentLLMProviderType.FAKE:
        return
    if provider_type == AgentLLMProviderType.NULL:
        return

    if api_key is None:
        raise ValueError("LLM provider requires api_key")


def _build_loop_config(
    loop: LoopConfigModel,
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
    event_output: EventOutputConfigModel,
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
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> str:
    value = _provider_env(provider_type, selected, "API_KEY", env)
    if value is not None:
        return value

    if provider.api_key is not None:
        return provider.api_key

    if provider.api_key_env is not None:
        value = env.get(provider.api_key_env)
        if value is None:
            raise ValueError(
                f"Missing environment variable for api_key_env: {provider.api_key_env}"
            )
        return value

    if provider.api_key_file is None:
        raise ValueError("LLM provider requires api_key")

    secret_path = Path(provider.api_key_file).expanduser()
    if not secret_path.exists():
        raise ValueError(f"Missing api_key_file: {_display_path(secret_path)}")
    return secret_path.read_text(encoding="utf-8").strip()


def _provider_timeout_seconds(
    *,
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> float:
    value = _provider_env(provider_type, selected, "TIMEOUT_SECONDS", env)
    if value is None:
        return provider.timeout_seconds
    return _positive_float_from_env(
        value,
        f"AGENT_{provider_type.value.upper()}_TIMEOUT_SECONDS",
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


def _provider_type(provider_id: str) -> AgentLLMProviderType:
    try:
        return AgentLLMProviderType(provider_id)
    except ValueError as exc:
        raise ValueError(f"Unsupported LLM provider: {provider_id}") from exc


def _env_bool(env_name: str, default: bool, env: Mapping[str, str]) -> bool:
    value = env.get(env_name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{env_name} must be a boolean")


def _env_positive_int(env_name: str, default: int, env: Mapping[str, str]) -> int:
    value = env.get(env_name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{env_name} must be a positive integer")
    return parsed


def _positive_float_from_env(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive number") from exc
    if parsed <= 0:
        raise ValueError(f"{label} must be a positive number")
    return parsed


def _display_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(expanded)
