from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMModelEnum,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig


class AgentNullLLMModel(AgentLLMModelEnum):
    NULL1 = ("null1", 100_000)


class AgentFakeLLMModel(AgentLLMModelEnum):
    MODEL1 = ("model1", 100_000)


@dataclass(frozen=True)
class AgentNullProvider(AgentLLMProviderConfig[AgentNullLLMModel]):
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.NULL

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentNullLLMModel):
            raise TypeError("Null LLM provider model must be an AgentNullLLMModel")


@dataclass(frozen=True)
class AgentFakeProvider(AgentLLMProviderConfig[AgentFakeLLMModel]):
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.FAKE

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentFakeLLMModel):
            raise TypeError("Fake LLM provider model must be an AgentFakeLLMModel")
