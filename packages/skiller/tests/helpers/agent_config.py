from pathlib import Path

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation
from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMProvider,
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
    tools: ToolRuntimeConfigs | None = None,
) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=AgentLLMProviderType.FAKE,
            providers=(
                AgentLLMProvider(
                    type=AgentLLMProviderType.FAKE,
                    model="model1",
                    api_key="test-key",
                    timeout_seconds=30,
                    context_window_tokens=100_000,
                ),
            ),
        ),
        loop=AgentLoopConfig(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
        context=AgentContextConfig(),
        event_output=AgentEventOutputConfig(),
        tools=tools or ToolRuntimeConfigs(),
    )


def agent_runner_config(
    *,
    system: str = "Be useful.",
    task: str = "Hi",
    tools: tuple[ToolDefinition, ...] | list[ToolDefinition] = (),
    max_turns: int = 1,
    max_tool_calls: int = 1,
) -> AgentRunnerConfig:
    tool_definitions = tuple(tools)
    return AgentRunnerConfig(
        system=system,
        task=task,
        tools=tool_definitions,
        config=agent_config(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
    )
