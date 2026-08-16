from pathlib import Path

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
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
from skiller.domain.agent.config.validation import AgentConfigValidation
from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    LLMModelDefinition,
    LLMProviderCatalog,
    OpenAILLMProviderDefinition,
)
from skiller.domain.tool.tool_contract import ToolDefinition, ToolRuntimeConfigs


class FakeAgentConfigPort:
    def __init__(
        self,
        config: AgentConfig | None = None,
        validation: AgentConfigValidation | None = None,
    ) -> None:
        self.config = config or agent_config()
        self.validation = validation or AgentConfigValidation.valid()
        self.config_paths: list[Path | None] = []
        self.validation_config_paths: list[Path | None] = []

    def get_config(self, *, config_path: Path | None = None) -> AgentConfig:
        self.config_paths.append(config_path)
        return self.config

    def validate_config(self, *, config_path: Path | None = None) -> AgentConfigValidation:
        self.validation_config_paths.append(config_path)
        return self.validation

    def list_provider_sources(self, *, config_path: Path | None = None) -> tuple:
        _ = config_path
        return ()

    def set_model(
        self,
        *,
        provider: str,
        model: str,
        config_path: Path | None = None,
    ) -> None:
        _ = provider, model, config_path


class FakeLLMProviderCatalogPort:
    def __init__(self, catalog: LLMProviderCatalog | None = None) -> None:
        self.catalog = catalog or fake_llm_provider_catalog()

    def get_catalog(self) -> LLMProviderCatalog:
        return self.catalog


def fake_llm_provider_definition() -> OpenAILLMProviderDefinition:
    return OpenAILLMProviderDefinition(
        name="fake",
        timeout_seconds=30,
        models=(LLMModelDefinition(model="model1", context_window_tokens=100_000),),
        enabled=True,
        base_url="http://localhost/v1",
        temperature=0,
        top_p=1,
        max_output_tokens=4096,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=None,
        options={},
    )


def fake_llm_provider_catalog() -> LLMProviderCatalog:
    return LLMProviderCatalog(providers=(fake_llm_provider_definition(),))


def agent_config(
    *,
    log_request: bool = False,
    log_request_file: str | None = None,
    max_turns: int = 1,
    max_tool_calls: int = 1,
    window_width_tokens: int = 100_000,
    tools: ToolRuntimeConfigs | None = None,
) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMSelection(provider="fake", model="model1"),
        loop=AgentLoopConfig(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
        context=AgentContextConfig(
            window_width_tokens=window_width_tokens,
            compaction=AgentContextCompactionConfig(
                compaction_trigger_ratio=0.8,
                compaction_target_ratio=0.5,
                keep_last_blocks=5,
            ),
        ),
        event_output=AgentEventOutputConfig(
            truncate=AgentEventOutputTruncateConfig(
                enabled=True,
                max_text_chars=100,
                max_json_chars=1000,
                max_array_items=10,
            ),
        ),
        debug=AgentDebugConfig(
            log_request=log_request,
            log_request_file=log_request_file,
            log_override_file=True,
        ),
        tools=tools or ToolRuntimeConfigs(),
    )


def agent_runner_config(
    *,
    log_request: bool = False,
    log_request_file: str | None = None,
    system: str = "Be useful.",
    task: str = "Hi",
    tools: tuple[ToolDefinition, ...] | list[ToolDefinition] = (),
    max_turns: int = 1,
    max_tool_calls: int = 1,
    window_width_tokens: int = 100_000,
) -> AgentRunnerConfig:
    tool_definitions = tuple(tools)
    return AgentRunnerConfig(
        system=system,
        task=task,
        tools=tool_definitions,
        config=agent_config(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
            window_width_tokens=window_width_tokens,
            log_request=log_request,
            log_request_file=log_request_file,
        ),
        provider_definition=fake_llm_provider_definition(),
    )
