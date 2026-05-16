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


class FakeAgentConfigPort:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or agent_config()

    def get_config(self) -> AgentConfig:
        return self.config


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
    context_id: str = "thread-1",
    tools: tuple[str, ...] | list[str] = (),
    max_turns: int = 1,
    max_tool_calls: int = 1,
) -> AgentRunnerConfig:
    return AgentRunnerConfig(
        system=system,
        task=task,
        context_id=context_id,
        tools=tuple(tools),
        config=agent_config(
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        ),
    )
