from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentLLMClientType,
    AgentLLMConfig,
    AgentLLMProviderConfig,
    AgentLLMProviderType,
    AgentLoopConfig,
)
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation
from skiller.domain.tool.tool_contract import ToolConfig


class FakeAgentConfigPort:
    def __init__(
        self,
        config: AgentConfig | None = None,
        validation: AgentConfigValidation | None = None,
    ) -> None:
        self.config = config or agent_config()
        self.validation = validation or AgentConfigValidation.valid()

    def get_config(self) -> AgentConfig:
        return self.config

    def validate_config(self) -> AgentConfigValidation:
        return self.validation


def agent_config(
    *,
    max_turns: int = 1,
    max_tool_calls: int = 1,
) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMConfig(
            default_provider="openai-main",
            providers={
                "openai-main": AgentLLMProviderConfig(
                    provider=AgentLLMProviderType.OPENAI,
                    client_type=AgentLLMClientType.OPENAI_CHAT_COMPLETIONS,
                    model="test-model",
                    api_key="test-key",
                    base_url="https://api.example.com/v1",
                    timeout_seconds=30,
                    context_window_tokens=100_000,
                )
            },
        ),
        loop=AgentLoopConfig(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
        context=AgentContextConfig(),
        event_output=AgentEventOutputConfig(),
    )


def agent_runner_config(
    *,
    system: str = "Be useful.",
    task: str = "Hi",
    tools: tuple[ToolConfig, ...] | list[ToolConfig] = (),
    max_turns: int = 1,
    max_tool_calls: int = 1,
) -> AgentRunnerConfig:
    return AgentRunnerConfig(
        system=system,
        task=task,
        tools=tuple(tools),
        config=agent_config(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
    )
