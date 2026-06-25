from typing import Protocol, TypeAlias, TypeVar

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.provider_lmstudio import LMStudioLLMRequest
from skiller.domain.agent.llm.provider_minimax import MiniMaxLLMRequest
from skiller.domain.agent.llm.request import LLMRequest

RequestT = TypeVar("RequestT", bound=LLMRequest, contravariant=True)


class LLMPort(Protocol[RequestT]):
    def generate(self, request: RequestT) -> LLMResponse: ...


ResolvedLLMPort: TypeAlias = (
    LLMPort[LLMRequest]
    | LLMPort[MiniMaxLLMRequest]
    | LLMPort[LMStudioLLMRequest]
    | LLMPort[CodexLLMRequest]
    | LLMPort[BedrockLLMRequest]
)
