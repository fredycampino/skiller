from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.agent.llm.model import (
    AgentLLMProviderType,
    LLMStaticModel,
)
from skiller.domain.agent.llm.provider import AgentLLMProviderConfig
from skiller.domain.agent.llm.request import LLMRequest


class AgentCodexLLMModel(LLMStaticModel):
    GPT_5_4 = ("gpt-5.4", 1_050_000)
    GPT_5_5 = ("gpt-5.5", 1_050_000)


CODEX_MODELS = (
    AgentCodexLLMModel.GPT_5_4,
    AgentCodexLLMModel.GPT_5_5,
)


@dataclass(frozen=True)
class CodexLLMRequest(LLMRequest):
    model: AgentCodexLLMModel
    parallel_tool_calls: bool

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentCodexLLMModel):
            raise TypeError("CodexLLMRequest model must be an AgentCodexLLMModel")


@dataclass(frozen=True)
class AgentCodexProvider(AgentLLMProviderConfig[AgentCodexLLMModel]):
    credentials_file: str

    type: ClassVar[AgentLLMProviderType] = AgentLLMProviderType.CODEX

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentCodexLLMModel):
            raise TypeError("Codex LLM provider model must be an AgentCodexLLMModel")
        super().__post_init__()
