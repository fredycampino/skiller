from typing import Protocol, TypeAlias, TypeVar

from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.agent.llm_request import (
    BedrockLLMRequest,
    CodexLLMRequest,
    LLMRequest,
    MiniMaxLLMRequest,
)

RequestT = TypeVar("RequestT", bound=LLMRequest, contravariant=True)


class LLMPort(Protocol[RequestT]):
    def generate(self, request: RequestT) -> LLMResponse: ...


ResolvedLLMPort: TypeAlias = (
    LLMPort[LLMRequest]
    | LLMPort[MiniMaxLLMRequest]
    | LLMPort[CodexLLMRequest]
    | LLMPort[BedrockLLMRequest]
)
