from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMProviderType,
    LLMStaticModel,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig


class AgentNullLLMModel(LLMStaticModel):
    NULL1 = ("null1", 100_000)


NULL_MODELS = (AgentNullLLMModel.NULL1,)


class AgentFakeLLMModel(LLMStaticModel):
    MODEL1 = ("model1", 100_000)


FAKE_MODELS = (AgentFakeLLMModel.MODEL1,)


@dataclass(frozen=True)
class AgentNullProvider(AgentLLMProviderConfig[AgentNullLLMModel]):
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.NULL

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentNullLLMModel):
            raise TypeError("Null LLM provider model must be an AgentNullLLMModel")
        super().__post_init__()


@dataclass(frozen=True)
class AgentFakeProvider(AgentLLMProviderConfig[AgentFakeLLMModel]):
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.FAKE

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentFakeLLMModel):
            raise TypeError("Fake LLM provider model must be an AgentFakeLLMModel")
        super().__post_init__()
