from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMModelEnum,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig
from skiller.domain.agent.llm.request import OpenAILLMRequest

LMSTUDIO_DEFAULT_API_KEY = "lm-studio"
LMSTUDIO_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
LMSTUDIO_LLM_TEMPERATURE = 0.2
LMSTUDIO_LLM_TOP_P = 1
LMSTUDIO_LLM_MAX_OUTPUT_TOKENS = 4096


class AgentLMStudioLLMModel(AgentLLMModelEnum):
    GEMMA_4_12B_QAT = ("google/gemma-4-12b-qat", 131_072)


@dataclass(frozen=True)
class LMStudioLLMRequest(OpenAILLMRequest):
    model: AgentLMStudioLLMModel

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentLMStudioLLMModel):
            raise TypeError("LMStudioLLMRequest model must be an AgentLMStudioLLMModel")


@dataclass(frozen=True)
class AgentLMStudioProvider(AgentLLMProviderConfig[AgentLMStudioLLMModel]):
    api_key: str = LMSTUDIO_DEFAULT_API_KEY
    base_url: str = LMSTUDIO_DEFAULT_BASE_URL

    temperature: ClassVar[float] = LMSTUDIO_LLM_TEMPERATURE
    top_p: ClassVar[float] = LMSTUDIO_LLM_TOP_P
    max_output_tokens: ClassVar[int] = LMSTUDIO_LLM_MAX_OUTPUT_TOKENS
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.LMSTUDIO

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentLMStudioLLMModel):
            raise TypeError("LM Studio LLM provider model must be an AgentLMStudioLLMModel")
        if not self.base_url.strip():
            raise ValueError("LM Studio LLM provider requires base_url")
