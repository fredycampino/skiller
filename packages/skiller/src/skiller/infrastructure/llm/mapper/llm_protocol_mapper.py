from typing import Protocol, TypeVar

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.request import LLMRequest

RequestT = TypeVar("RequestT", bound=LLMRequest, contravariant=True)
RawResponseT = TypeVar("RawResponseT", contravariant=True)


class LLMProtocolMapper(Protocol[RequestT, RawResponseT]):
    def to_kwargs(self, request: RequestT) -> dict[str, object]: ...

    def to_response(
        self,
        raw_response: RawResponseT,
        *,
        request: RequestT,
    ) -> LLMResponse: ...
