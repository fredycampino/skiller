from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from skiller.domain.agent.llm.model import (
    LLMModelLike,
    LLMToolChoiceMode,
)

DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS = True
DEFAULT_AGENT_LLM_TOOL_CHOICE = LLMToolChoiceMode.AUTO
TOOL_RESULT_APPROX_BYTES_PER_TOKEN = 4
TOOL_RESULT_CONTEXT_RATIO = 0.10
TOOL_RESULT_MAX_BYTES = 50_000

ModelT = TypeVar("ModelT", bound=LLMModelLike)


@dataclass(frozen=True)
class AgentLLMProviderConfig(Generic[ModelT]):
    model: ModelT
    models: tuple[ModelT, ...]
    timeout_seconds: float
    window_width_tokens: int

    parallel_tool_calls: ClassVar[bool] = DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS
    tool_choice: ClassVar[LLMToolChoiceMode] = DEFAULT_AGENT_LLM_TOOL_CHOICE

    def __post_init__(self) -> None:
        if not self.models:
            raise ValueError("LLM provider models must not be empty")
        allowed_model_values = {model.value for model in self.models}
        if self.model.value not in allowed_model_values:
            raise ValueError(f"LLM provider model is not allowed: {self.model.value}")

    @property
    def model_max_tokens(self) -> int:
        return min(
            self.window_width_tokens,
            self.model.model_context_window_tokens,
        )

    def context_max_tokens(self, *, ratio: float) -> int:
        return int(self.model_max_tokens * ratio)

    @property
    def tool_result_max_bytes(self) -> int:
        return min(
            TOOL_RESULT_MAX_BYTES,
            int(
                self.model_max_tokens
                * TOOL_RESULT_CONTEXT_RATIO
                * TOOL_RESULT_APPROX_BYTES_PER_TOKEN
            ),
        )
