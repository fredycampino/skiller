from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMModelEnum,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig
from skiller.domain.agent.llm.request import LLMRequest


class AgentBedrockLLMModel(AgentLLMModelEnum):
    CLAUDE_OPUS_4_6 = ("us.anthropic.claude-opus-4-6-v1", 200_000)
    CLAUDE_OPUS_4_7 = ("us.anthropic.claude-opus-4-7", 200_000)
    CLAUDE_OPUS_4_8 = ("us.anthropic.claude-opus-4-8", 200_000)
    CLAUDE_OPUS_4_5 = ("us.anthropic.claude-opus-4-5-20251101-v1:0", 200_000)
    CLAUDE_OPUS_4_1 = ("us.anthropic.claude-opus-4-1-20250805-v1:0", 200_000)
    CLAUDE_SONNET_4_6 = ("us.anthropic.claude-sonnet-4-6", 200_000)
    CLAUDE_SONNET_4_5 = ("us.anthropic.claude-sonnet-4-5-20250929-v1:0", 200_000)
    CLAUDE_HAIKU_4_5 = ("us.anthropic.claude-haiku-4-5-20251001-v1:0", 200_000)
    CLAUDE_FABLE_5 = ("us.anthropic.claude-fable-5", 200_000)


@dataclass(frozen=True)
class BedrockLLMRequest(LLMRequest):
    model: AgentBedrockLLMModel

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentBedrockLLMModel):
            raise TypeError("BedrockLLMRequest model must be an AgentBedrockLLMModel")


@dataclass(frozen=True)
class AgentBedrockProvider(AgentLLMProviderConfig[AgentBedrockLLMModel]):
    profile: str

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.BEDROCK

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentBedrockLLMModel):
            raise TypeError("Bedrock LLM provider model must be an AgentBedrockLLMModel")
        if not self.profile.strip():
            raise ValueError("Bedrock LLM provider requires profile")
