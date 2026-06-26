from __future__ import annotations

from dataclasses import dataclass, field

from skiller.domain.agent.llm.model import (
    LLMMessage,
    LLMModelLike,
    LLMResponseFormat,
    LLMToolChoiceMode,
    validate_llm_model_like,
)
from skiller.domain.tool.tool_contract import ToolDefinition


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: LLMModelLike
    tools: tuple[ToolDefinition, ...] = field(default=(), kw_only=True)
    response_format: LLMResponseFormat | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        validate_llm_model_like(self.model, label="LLMRequest model")


@dataclass(frozen=True)
class OpenAILLMRequest(LLMRequest):
    model: LLMModelLike
    tool_choice: LLMToolChoiceMode
    parallel_tool_calls: bool
    temperature: float
    max_tokens: int
    top_p: float

    def __post_init__(self) -> None:
        super().__post_init__()
