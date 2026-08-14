from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from skiller.domain.agent.config.model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentDebugConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.llm.model import LLMCustomModel, LLMModelLike
from skiller.domain.agent.llm.provider_lmstudio import (
    LMSTUDIO_DEFAULT_API_KEY,
    LMSTUDIO_DEFAULT_BASE_URL,
)
from skiller.domain.agent.llm.provider_registry import (
    BEDROCK_MODELS,
    CODEX_MODELS,
    FAKE_MODELS,
    MINIMAX_MODELS,
    MOONSHOT_MODELS,
    NULL_MODELS,
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
    AgentLMStudioProvider,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
    AgentMoonshotLLMModel,
    AgentMoonshotProvider,
    AgentNullLLMModel,
    AgentNullProvider,
)
from skiller.domain.tool.tool_contract import (
    ConfiguredTool,
    ToolDefinition,
    ToolRuntimeConfig,
    ToolRuntimeConfigs,
)
from skiller.infrastructure.config.agent_config_schema import (
    AgentConfigModel,
    DebugConfigModel,
    EventOutputConfigModel,
    LLMProviderConfigModel,
    LoopConfigModel,
)

DEFAULT_LLM_REQUEST_LOG_FILE = "~/.skiller/logs/request/{provider}/request.json"


class AgentConfigMapper:
    def __init__(
        self,
        *,
        env: Mapping[str, str],
        tools: tuple[ToolDefinition, ...] = (),
    ) -> None:
        self.env = env
        self.tools = tools

    def from_json(
        self,
        raw_config: dict[str, object],
        *,
        tools_base_path: Path,
    ) -> AgentConfig:
        if "agent" in raw_config:
            raise ValueError("agent.json field 'agent' is not supported")

        try:
            config = AgentConfigModel.model_validate(
                _config_with_known_providers(raw_config)
            )
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

        llm = AgentLLMProviderList(
            default_provider=default_provider,
            providers=tuple(providers),
        )
        window_width_tokens = config.context.window_width_tokens
        if window_width_tokens is None:
            window_width_tokens = llm.default().model.model_context_window_tokens

        compaction = AgentContextCompactionConfig(
            compaction_trigger_ratio=config.context.compaction.compaction_trigger_ratio,
            compaction_target_ratio=config.context.compaction.compaction_target_ratio,
            keep_last_blocks=config.context.compaction.keep_last_blocks,
        )
        context = AgentContextConfig(
            window_width_tokens=window_width_tokens,
            compaction=compaction,
        )
        debug = AgentDebugConfig(
            log_request=config.debug.log_request,
            log_request_file=_resolve_log_request_file(
                debug_config=config.debug,
                default_provider=default_provider,
            ),
            log_override_file=config.debug.log_override_file,
        )
        loop = _build_loop_config(config.loop, env=self.env)
        event_output = _build_event_output_config(config.event_output, env=self.env)
        tools = _build_tool_runtime_configs(
            raw_tools=config.tools,
            tools=self.tools,
            base_path=tools_base_path,
        )

        return AgentConfig(
            llm=llm,
            loop=loop,
            context=context,
            event_output=event_output,
            debug=debug,
            tools=tools,
        )


def _resolve_log_request_file(
    *,
    debug_config: DebugConfigModel,
    default_provider: AgentLLMProviderType,
) -> str:
    if debug_config.log_request_file is None or not debug_config.log_request_file.strip():
        return DEFAULT_LLM_REQUEST_LOG_FILE.format(provider=default_provider.value)
    return debug_config.log_request_file


def _build_provider(
    *,
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
) -> AgentLLMProvider:
    raw_model = _provider_env(provider_type, selected, "MODEL", env) or provider.model
    timeout_seconds = _provider_timeout_seconds(
        provider_type=provider_type,
        provider=provider,
        selected=selected,
        env=env,
    )
    if provider.models is not None and provider_type != AgentLLMProviderType.LMSTUDIO:
        raise ValueError(
            f"Provider models config is not supported for provider='{provider_type.value}'"
        )

    if provider_type == AgentLLMProviderType.NULL:
        return AgentNullProvider(
            model=_null_model(raw_model),
            models=NULL_MODELS,
            timeout_seconds=timeout_seconds,
        )
    if provider_type == AgentLLMProviderType.FAKE:
        return AgentFakeProvider(
            model=_fake_model(raw_model),
            models=FAKE_MODELS,
            timeout_seconds=timeout_seconds,
        )
    if provider_type == AgentLLMProviderType.MINIMAX:
        api_key = _resolve_api_key(
            provider_type=provider_type,
            provider=provider,
            selected=selected,
            env=env,
        )
        return AgentMiniMaxProvider(
            model=_minimax_model(raw_model),
            models=MINIMAX_MODELS,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
    if provider_type == AgentLLMProviderType.MOONSHOT:
        api_key = _resolve_api_key(
            provider_type=provider_type,
            provider=provider,
            selected=selected,
            env=env,
        )
        return AgentMoonshotProvider(
            model=_moonshot_model(raw_model),
            models=MOONSHOT_MODELS,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
    if provider_type == AgentLLMProviderType.LMSTUDIO:
        lmstudio_models = _lmstudio_models(provider)
        return AgentLMStudioProvider(
            model=_lmstudio_model(raw_model, models=lmstudio_models),
            models=lmstudio_models,
            api_key=_optional_api_key(
                provider_type=provider_type,
                provider=provider,
                selected=selected,
                env=env,
                default=LMSTUDIO_DEFAULT_API_KEY,
            ),
            base_url=_optional_base_url(
                provider_type=provider_type,
                provider=provider,
                selected=selected,
                env=env,
                default=LMSTUDIO_DEFAULT_BASE_URL,
            ),
            timeout_seconds=timeout_seconds,
        )
    if provider_type == AgentLLMProviderType.CODEX:
        return AgentCodexProvider(
            model=_codex_model(raw_model),
            models=CODEX_MODELS,
            credentials_file=_required_credentials_file(provider.credentials_file),
            timeout_seconds=timeout_seconds,
        )
    if provider_type == AgentLLMProviderType.BEDROCK:
        return AgentBedrockProvider(
            model=_bedrock_model(raw_model),
            models=BEDROCK_MODELS,
            profile=_required_profile(provider.profile),
            timeout_seconds=timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM provider: {provider_type.value}")


def _build_tool_runtime_configs(
    *,
    raw_tools: dict[str, dict[str, object]],
    tools: tuple[ToolDefinition, ...],
    base_path: Path,
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
        runtime_config_items.append(
            tool.to_runtime_config(
                raw_tool,
                base_path=base_path,
            )
        )
    return ToolRuntimeConfigs(items=tuple(runtime_config_items))


def _null_model(value: str) -> AgentNullLLMModel:
    try:
        return AgentNullLLMModel(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported model='{value}' for provider='null'") from exc


def _fake_model(value: str) -> AgentFakeLLMModel:
    try:
        return AgentFakeLLMModel(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported model='{value}' for provider='fake'") from exc


def _minimax_model(value: str) -> AgentMiniMaxLLMModel:
    try:
        return AgentMiniMaxLLMModel(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported model='{value}' for provider='minimax'") from exc


def _moonshot_model(value: str) -> AgentMoonshotLLMModel:
    try:
        return AgentMoonshotLLMModel(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported model='{value}' for provider='moonshot'") from exc


def _codex_model(value: str) -> AgentCodexLLMModel:
    try:
        return AgentCodexLLMModel(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported model='{value}' for provider='codex'") from exc


def _lmstudio_models(provider: LLMProviderConfigModel) -> tuple[LLMModelLike, ...]:
    if provider.models is None:
        raise ValueError("LM Studio LLM provider requires models")

    model_values = [model.model for model in provider.models]
    duplicate_values = sorted(
        {
            model_value
            for model_value in model_values
            if model_values.count(model_value) > 1
        }
    )
    if duplicate_values:
        duplicate_text = ", ".join(duplicate_values)
        raise ValueError(f"Duplicate LM Studio models: {duplicate_text}")

    return tuple(
        LLMCustomModel(
            value=model.model,
            model_context_window_tokens=model.context_window_tokens,
        )
        for model in provider.models
    )


def _lmstudio_model(value: str, *, models: tuple[LLMModelLike, ...]) -> LLMModelLike:
    for model in models:
        if model.value == value:
            return model
    configured_models = ", ".join(model.value for model in models)
    raise ValueError(
        f"LM Studio selected model='{value}' is not listed in configured models: "
        f"{configured_models}"
    )


def _bedrock_model(value: str) -> AgentBedrockLLMModel:
    try:
        return AgentBedrockLLMModel(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported model='{value}' for provider='bedrock'") from exc


def _required_credentials_file(credentials_file: str | None) -> str:
    if credentials_file is None or not credentials_file.strip():
        raise ValueError("LLM provider requires credentials_file")
    return credentials_file


def _required_profile(profile: str | None) -> str:
    if profile is None or not profile.strip():
        raise ValueError("LLM provider requires profile")
    return profile


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


def _optional_api_key(
    *,
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
    default: str,
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
    if provider.api_key_file is not None:
        secret_path = Path(provider.api_key_file).expanduser()
        if not secret_path.exists():
            raise ValueError(f"Missing api_key_file: {_display_path(secret_path)}")
        return secret_path.read_text(encoding="utf-8").strip()
    return default


def _optional_base_url(
    *,
    provider_type: AgentLLMProviderType,
    provider: LLMProviderConfigModel,
    selected: bool,
    env: Mapping[str, str],
    default: str,
) -> str:
    value = _provider_env(provider_type, selected, "BASE_URL", env)
    if value is not None:
        return value
    if provider.base_url is not None:
        return provider.base_url
    return default


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


def _config_with_known_providers(
    raw_config: dict[str, object],
) -> dict[str, object]:
    providers = raw_config.get("providers")
    if not isinstance(providers, dict):
        return raw_config

    return {
        **raw_config,
        "providers": {
            provider_id: provider
            for provider_id, provider in providers.items()
            if isinstance(provider_id, str)
            and _known_provider_type(provider_id) is not None
        },
    }


def _known_provider_type(provider_id: str) -> AgentLLMProviderType | None:
    try:
        return AgentLLMProviderType(provider_id)
    except ValueError:
        return None


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
