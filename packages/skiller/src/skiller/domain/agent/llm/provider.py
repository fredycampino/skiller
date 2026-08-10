from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from skiller.domain.agent.llm.model import (
    LLMModelLike,
    LLMToolChoiceMode,
)

DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS = True
DEFAULT_AGENT_LLM_TOOL_CHOICE = LLMToolChoiceMode.AUTO

ModelT = TypeVar("ModelT", bound=LLMModelLike)


@dataclass(frozen=True)
class AgentLLMProviderConfig(Generic[ModelT]):
    model: ModelT
    models: tuple[ModelT, ...]
    timeout_seconds: float
    parallel_tool_calls: ClassVar[bool] = DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS
    tool_choice: ClassVar[LLMToolChoiceMode] = DEFAULT_AGENT_LLM_TOOL_CHOICE

    def __post_init__(self) -> None:
        if not self.models:
            raise ValueError("LLM provider models must not be empty")
        allowed_model_values = {model.value for model in self.models}
        if self.model.value not in allowed_model_values:
            raise ValueError(f"LLM provider model is not allowed: {self.model.value}")
