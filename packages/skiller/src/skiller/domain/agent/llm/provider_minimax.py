from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMProviderType,
    LLMStaticModel,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig
from skiller.domain.agent.llm.request import OpenAILLMRequest

MINIMAX_LLM_TEMPERATURE = 1
MINIMAX_LLM_TOP_P = 1
MINIMAX_LLM_MAX_OUTPUT_TOKENS = 4096


class AgentMiniMaxLLMModel(LLMStaticModel):
    M2_5 = ("MiniMax-M2.5", 204_800)
    M2_7 = ("MiniMax-M2.7", 204_800)


MINIMAX_MODELS = (
    AgentMiniMaxLLMModel.M2_5,
    AgentMiniMaxLLMModel.M2_7,
)


@dataclass(frozen=True)
class MiniMaxLLMRequest(OpenAILLMRequest):
    model: AgentMiniMaxLLMModel

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentMiniMaxLLMModel):
            raise TypeError("MiniMaxLLMRequest model must be an AgentMiniMaxLLMModel")


@dataclass(frozen=True)
class AgentMiniMaxProvider(AgentLLMProviderConfig[AgentMiniMaxLLMModel]):
    api_key: str

    temperature: ClassVar[float] = MINIMAX_LLM_TEMPERATURE
    top_p: ClassVar[float] = MINIMAX_LLM_TOP_P
    max_output_tokens: ClassVar[int] = MINIMAX_LLM_MAX_OUTPUT_TOKENS
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.MINIMAX

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentMiniMaxLLMModel):
            raise TypeError("MiniMax LLM provider model must be an AgentMiniMaxLLMModel")
        super().__post_init__()
