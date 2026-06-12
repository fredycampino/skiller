from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Generic, TypeVar

from skiller.domain.agent.agent_llm_generation_model import LLMToolChoiceMode
from skiller.domain.agent.agent_llm_model_enum import AgentLLMModelEnum

DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS = True
DEFAULT_AGENT_LLM_TOOL_CHOICE = LLMToolChoiceMode.AUTO

ModelT = TypeVar("ModelT", bound=AgentLLMModelEnum)


class AgentLLMProviderType(str, Enum):
    NULL = "null"
    FAKE = "fake"
    MINIMAX = "minimax"
    CODEX = "codex"
    BEDROCK = "bedrock"


@dataclass(frozen=True)
class AgentLLMProviderConfig(Generic[ModelT]):
    model: ModelT
    timeout_seconds: float
    window_width_tokens: int

    parallel_tool_calls: ClassVar[bool] = DEFAULT_AGENT_LLM_PARALLEL_TOOL_CALLS
    tool_choice: ClassVar[LLMToolChoiceMode] = DEFAULT_AGENT_LLM_TOOL_CHOICE
