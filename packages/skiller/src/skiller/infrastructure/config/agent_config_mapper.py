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
    AgentLLMSelection,
    AgentLoopConfig,
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

        config_payload = _strip_legacy_provider_configuration(raw_config)

        try:
            config = AgentConfigModel.model_validate(config_payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid agent config: {exc}") from exc

        llm = AgentLLMSelection(
            provider=config.llm.provider,
            model=config.llm.model,
        )

        compaction = AgentContextCompactionConfig(
            compaction_trigger_ratio=config.context.compaction.compaction_trigger_ratio,
            compaction_target_ratio=config.context.compaction.compaction_target_ratio,
            keep_last_blocks=config.context.compaction.keep_last_blocks,
        )
        context = AgentContextConfig(
            window_width_tokens=config.context.window_width_tokens,
            compaction=compaction,
        )
        debug = AgentDebugConfig(
            log_request=config.debug.log_request,
            log_streaming=config.debug.log_streaming,
            log_request_file=_resolve_log_request_file(
                debug_config=config.debug,
                provider=config.llm.provider,
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


def _strip_legacy_provider_configuration(
    raw_config: dict[str, object],
) -> dict[str, object]:
    """Ignore provider settings from pre-provider-catalog agent.json files."""
    config_payload = dict(raw_config)
    config_payload.pop("providers", None)
    llm_payload = config_payload.get("llm")
    if isinstance(llm_payload, dict):
        config_payload["llm"] = {
            key: value
            for key, value in llm_payload.items()
            if key != "default_provider"
        }
    return config_payload


def _resolve_log_request_file(
    *,
    debug_config: DebugConfigModel,
    provider: str,
) -> str:
    if debug_config.log_request_file is None or not debug_config.log_request_file.strip():
        return DEFAULT_LLM_REQUEST_LOG_FILE.format(provider=provider)
    return debug_config.log_request_file


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
