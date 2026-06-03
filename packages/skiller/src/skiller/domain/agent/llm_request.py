from __future__ import annotations

from dataclasses import dataclass, field

from skiller.domain.agent.agent_llm_generation_model import LLMToolChoiceMode
from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexLLMModel,
    AgentLLMModel,
    AgentLLMModelEnum,
    AgentMiniMaxLLMModel,
)
from skiller.domain.agent.llm_model import LLMMessage, LLMResponseFormat
from skiller.domain.tool.tool_contract import ToolDefinition


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: AgentLLMModel
    tools: tuple[ToolDefinition, ...] = field(default=(), kw_only=True)
    response_format: LLMResponseFormat | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentLLMModelEnum):
            raise TypeError("LLMRequest model must be an AgentLLMModel enum")


@dataclass(frozen=True)
class MiniMaxLLMRequest(LLMRequest):
    model: AgentMiniMaxLLMModel
    tool_choice: LLMToolChoiceMode
    parallel_tool_calls: bool
    temperature: float
    max_tokens: int
    top_p: float

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentMiniMaxLLMModel):
            raise TypeError("MiniMaxLLMRequest model must be an AgentMiniMaxLLMModel")


@dataclass(frozen=True)
class CodexLLMRequest(LLMRequest):
    model: AgentCodexLLMModel
    parallel_tool_calls: bool

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentCodexLLMModel):
            raise TypeError("CodexLLMRequest model must be an AgentCodexLLMModel")
