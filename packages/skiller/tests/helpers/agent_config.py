from pathlib import Path

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.domain.agent.config.model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.config.validation import AgentConfigValidation
from skiller.domain.agent.llm.provider_registry import (
    FAKE_MODELS,
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
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


def agent_config(
    *,
    max_turns: int = 1,
    max_tool_calls: int = 1,
    window_width_tokens: int = 100_000,
    tools: ToolRuntimeConfigs | None = None,
) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=AgentLLMProviderType.FAKE,
            providers=(
                AgentFakeProvider(
                    model=AgentFakeLLMModel.MODEL1,
                    models=FAKE_MODELS,
                    timeout_seconds=30,
                    window_width_tokens=window_width_tokens,
                ),
            ),
        ),
        loop=AgentLoopConfig(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
        context=AgentContextConfig(
            compaction=AgentContextCompactionConfig(
                enabled=False,
                max_total_tokens_ratio=0.8,
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
        tools=tools or ToolRuntimeConfigs(),
    )


def agent_runner_config(
    *,
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
        ),
    )
