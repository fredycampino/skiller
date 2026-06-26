from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMProviderType,
    LLMModelLike,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig
from skiller.domain.agent.llm.request import OpenAILLMRequest

LMSTUDIO_DEFAULT_API_KEY = "lm-studio"
LMSTUDIO_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
LMSTUDIO_LLM_TEMPERATURE = 0.2
LMSTUDIO_LLM_TOP_P = 1
LMSTUDIO_LLM_MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class LMStudioLLMRequest(OpenAILLMRequest):
    model: LLMModelLike

    def __post_init__(self) -> None:
        super().__post_init__()


@dataclass(frozen=True)
class AgentLMStudioProvider(AgentLLMProviderConfig[LLMModelLike]):
    api_key: str = LMSTUDIO_DEFAULT_API_KEY
    base_url: str = LMSTUDIO_DEFAULT_BASE_URL

    temperature: ClassVar[float] = LMSTUDIO_LLM_TEMPERATURE
    top_p: ClassVar[float] = LMSTUDIO_LLM_TOP_P
    max_output_tokens: ClassVar[int] = LMSTUDIO_LLM_MAX_OUTPUT_TOKENS
    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.LMSTUDIO

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.base_url.strip():
            raise ValueError("LM Studio LLM provider requires base_url")
