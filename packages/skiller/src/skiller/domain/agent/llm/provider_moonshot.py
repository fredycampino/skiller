from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMProviderType,
    LLMStaticModel,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig
from skiller.domain.agent.llm.request import OpenAILLMRequest

MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"
MOONSHOT_LLM_TEMPERATURE = 1
MOONSHOT_LLM_TOP_P = 0.95
MOONSHOT_LLM_MAX_OUTPUT_TOKENS = 4096


class AgentMoonshotLLMModel(LLMStaticModel):
    KIMI_K3 = ("kimi-k3", 256_000)
    KIMI_K2_7_CODE = ("kimi-k2.7-code", 256_000)


MOONSHOT_MODELS = (
    AgentMoonshotLLMModel.KIMI_K3,
    AgentMoonshotLLMModel.KIMI_K2_7_CODE,
)


@dataclass(frozen=True)
class MoonshotLLMRequest(OpenAILLMRequest):
    model: AgentMoonshotLLMModel

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentMoonshotLLMModel):
            raise TypeError("MoonshotLLMRequest model must be an AgentMoonshotLLMModel")


@dataclass(frozen=True)
class AgentMoonshotProvider(AgentLLMProviderConfig[AgentMoonshotLLMModel]):
    api_key: str

    temperature: ClassVar[float] = MOONSHOT_LLM_TEMPERATURE
    top_p: ClassVar[float] = MOONSHOT_LLM_TOP_P
    max_output_tokens: ClassVar[int] = MOONSHOT_LLM_MAX_OUTPUT_TOKENS
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.MOONSHOT

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentMoonshotLLMModel):
            raise TypeError("Moonshot LLM provider model must be an AgentMoonshotLLMModel")
        super().__post_init__()
