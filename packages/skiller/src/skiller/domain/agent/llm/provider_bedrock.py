from dataclasses import dataclass

from skiller.domain.agent.llm.model import LLMModelLike
from skiller.domain.agent.llm.request import LLMRequest


@dataclass(frozen=True)
class BedrockLLMRequest(LLMRequest):
    model: LLMModelLike
    max_tokens: int

    def __post_init__(self) -> None:
        super().__post_init__()
