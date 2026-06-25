from dataclasses import dataclass
from typing import TypeAlias

from skiller.domain.agent.llm.model import AgentLLMProviderType
from skiller.domain.agent.llm.provider_bedrock import (
    AgentBedrockLLMModel,
    AgentBedrockProvider,
)
from skiller.domain.agent.llm.provider_codex import (
    AgentCodexLLMModel,
    AgentCodexProvider,
)
from skiller.domain.agent.llm.provider_defaults import (
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentNullLLMModel,
    AgentNullProvider,
)
from skiller.domain.agent.llm.provider_lmstudio import (
    AgentLMStudioLLMModel,
    AgentLMStudioProvider,
)
from skiller.domain.agent.llm.provider_minimax import (
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
)

AgentLLMModel: TypeAlias = (
    AgentNullLLMModel
    | AgentFakeLLMModel
    | AgentMiniMaxLLMModel
    | AgentLMStudioLLMModel
    | AgentCodexLLMModel
    | AgentBedrockLLMModel
)


def agent_llm_model_from_value(value: str) -> AgentLLMModel:
    model_types = (
        AgentNullLLMModel,
        AgentFakeLLMModel,
        AgentMiniMaxLLMModel,
        AgentLMStudioLLMModel,
        AgentCodexLLMModel,
        AgentBedrockLLMModel,
    )
    for model_type in model_types:
        try:
            return model_type(value)
        except ValueError:
            continue

    raise ValueError(f"Unsupported LLM model: {value}")


AgentLLMProvider: TypeAlias = (
    AgentNullProvider
    | AgentFakeProvider
    | AgentMiniMaxProvider
    | AgentLMStudioProvider
    | AgentCodexProvider
    | AgentBedrockProvider
)


@dataclass(frozen=True)
class AgentLLMProviderList:
    default_provider: AgentLLMProviderType
    providers: tuple[AgentLLMProvider, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            raise RuntimeError("LLM providers must not be empty")

        for provider in self.providers:
            if provider.type == self.default_provider:
                return

        raise RuntimeError(
            f"Missing default LLM provider config: {self.default_provider.value}"
        )

    def default(self) -> AgentLLMProvider:
        for provider in self.providers:
            if provider.type == self.default_provider:
                return provider

        raise RuntimeError(
            f"Missing default LLM provider config: {self.default_provider.value}"
        )
