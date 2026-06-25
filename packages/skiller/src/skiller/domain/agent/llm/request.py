from __future__ import annotations

from dataclasses import dataclass, field

from skiller.domain.agent.llm.model import (
    AgentLLMModelEnum,
    LLMMessage,
    LLMResponseFormat,
    LLMToolChoiceMode,
)
from skiller.domain.tool.tool_contract import ToolDefinition


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: AgentLLMModelEnum
    tools: tuple[ToolDefinition, ...] = field(default=(), kw_only=True)
    response_format: LLMResponseFormat | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.model, AgentLLMModelEnum):
            raise TypeError("LLMRequest model must be an AgentLLMModel enum")


@dataclass(frozen=True)
class OpenAILLMRequest(LLMRequest):
    model: AgentLLMModelEnum
    tool_choice: LLMToolChoiceMode
    parallel_tool_calls: bool
    temperature: float
    max_tokens: int
    top_p: float

    def __post_init__(self) -> None:
        super().__post_init__()
