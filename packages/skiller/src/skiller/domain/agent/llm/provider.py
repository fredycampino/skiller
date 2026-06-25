from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from skiller.domain.agent.llm.model import (
    AgentLLMModelEnum,
    LLMToolChoiceMode,
)

DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS = True
DEFAULT_AGENT_LLM_TOOL_CHOICE = LLMToolChoiceMode.AUTO

ModelT = TypeVar("ModelT", bound=AgentLLMModelEnum)


@dataclass(frozen=True)
class AgentLLMProviderConfig(Generic[ModelT]):
    model: ModelT
    timeout_seconds: float
    window_width_tokens: int

    parallel_tool_calls: ClassVar[bool] = DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS
    tool_choice: ClassVar[LLMToolChoiceMode] = DEFAULT_AGENT_LLM_TOOL_CHOICE
