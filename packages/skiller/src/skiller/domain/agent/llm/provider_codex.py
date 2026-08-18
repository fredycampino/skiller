from dataclasses import dataclass

from skiller.domain.agent.llm.model import LLMModelLike
from skiller.domain.agent.llm.request import LLMRequest


@dataclass(frozen=True)
class CodexLLMRequest(LLMRequest):
    model: LLMModelLike
    parallel_tool_calls: bool
    session_id: str

    def __post_init__(self) -> None:
        super().__post_init__()
